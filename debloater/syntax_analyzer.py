#!/usr/bin/env python3
import logging
from jpamb.jvm.base import AbsMethodID
import tree_sitter
import tree_sitter_java
import jpamb
import sys
from pathlib import Path
from tree_sitter import Query, QueryCursor

# TODO: Expected output of this whole thing:
# A list of Method ID STRINGS, which are in the following format:
# "jpamb.cases.Bloated.unreachableBranchBasic:(I)I"
# For reference: check debloat.py, because I have the input of my static analyzer as the "called" array there. That is the format i need

log = logging
log.basicConfig(level=logging.DEBUG)

class QueryRegistry:
    JAVA_LANGUAGE = tree_sitter.Language(tree_sitter_java.language())

    @staticmethod
    def class_query(simple_classname: str) -> Query:
        return Query(
            QueryRegistry.JAVA_LANGUAGE,
            f"""
            (class_declaration 
                name: ((identifier) @class-name 
                      (#eq? @class-name "{simple_classname}"))) @class
            """,
        )

    @staticmethod
    def method_query(method_name: str) -> Query:
        return Query(
            QueryRegistry.JAVA_LANGUAGE,
            f"""
            (method_declaration 
                name: ((identifier) @method-name 
                      (#eq? @method-name "{method_name}"))
            ) @method
            """,
        )

    @staticmethod
    def methods_query() -> Query:
        return Query(
            QueryRegistry.JAVA_LANGUAGE,
            """
            (method_declaration
                name: (identifier) @method-name
                body: (block) @method-body) @method
            """
        )

    @staticmethod
    def calls_query() -> Query:
        return Query(
            QueryRegistry.JAVA_LANGUAGE,
            """
            (method_invocation
                name: (identifier) @callee)
            """
        )
    
    @staticmethod
    def import_query() -> Query:
        return Query(
            QueryRegistry.JAVA_LANGUAGE,
            """
            (import_declaration
                (scoped_identifier) @import-name)
            """
        )

class Method:
    # Store method metadata
    def __init__(self, file_path: str, methodname: str, start_line: int, end_line: int):
        self.file_path = file_path
        self.methodname = methodname
        self.start_line = start_line
        self.end_line = end_line

class MethodAnalyzer:
    def __init__(self, root: str, method_id: AbsMethodID):
        self.root = Path(root).resolve()
        self.method_id = method_id
        self.parser = tree_sitter.Parser(QueryRegistry.JAVA_LANGUAGE)
        self.call_graph: dict[str, set[str]] = {}
        self.all_methods_qualified: set[str] = set()
        self.called_simple: set[str] = set()
        self.methods: dict[str, Method] = {}
        self._methods_q = QueryRegistry.methods_query()
        self._calls_q = QueryRegistry.calls_query()

    def input_check(self) -> bool:
        srcfile = jpamb.sourcefile(self.method_id).relative_to(Path.cwd())
        with open(srcfile, "rb") as f:
            log.debug("parse sourcefile %s", srcfile)
            tree = self.parser.parse(f.read())
        simple_classname = str(self.method_id.classname.name)

        class_nodes = QueryCursor(QueryRegistry.class_query(simple_classname)).captures(tree.root_node).get("class", [])
        if not class_nodes:
            log.error(f"could not find a class of name {simple_classname} in {srcfile}")
            return False

        method_name = self.method_id.extension.name
        for cls in class_nodes:
            for node in QueryCursor(QueryRegistry.method_query(method_name)).captures(cls).get("method", []):
                p = node.child_by_field_name("parameters")
                if not p:
                    continue
                params = [c for c in p.children if c.type == "formal_parameter"]
                if len(params) != len(self.method_id.extension.params):
                    continue
                return True

        log.warning(f"could not find a method of name {method_name} in {simple_classname}")
        return False

    def _get_imports(self, t: tree_sitter.Tree) -> list[str]:
        names: list[str] = []
        for n in QueryCursor(QueryRegistry.import_query()).captures(t.root_node).get("import-name", []):
            text = n.text.decode()
            if text.endswith(".*"):
                text = text[:-2]
            names.append(text)
        return names
    
    def _resolve_import_to_path(self, imp: str, src_root: Path) -> Path | None:
        rel = Path(imp.replace(".", "/"))
        for ext in (".java", ".Java"):
            cand = src_root / (str(rel) + ext)
            if cand.exists():
                return cand
        return None
    
    def _enclosing_class_name(self, n: tree_sitter.Node) -> str | None:
        p = n
        while p is not None:
            if p.type == "class_declaration":
                cname = p.child_by_field_name("name")
                return cname.text.decode() if cname and cname.text else None
            p = p.parent
        return None
    
    def collect_reachable(self, graph: dict[str, set[str]], roots: list[str]) -> set[str]:
        seen: set[str] = set()
        stack: list[str] = [r for r in roots if r]
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            stack.extend(graph.get(n, ()))
        return seen
    
    def _extract_methods_and_calls(self, fpath: Path, ftree: tree_sitter.Tree):
        for md in QueryCursor(self._methods_q).captures(ftree.root_node).get("method", []):
            name_nodes = QueryCursor(self._methods_q).captures(md).get("method-name", [])
            if not name_nodes:
                continue
            mname = name_nodes[0].text.decode()

            cname = self._enclosing_class_name(md)
            qname = f"{cname}.{mname}" if cname else mname
            self.all_methods_qualified.add(qname)

            try:
                rel_path = fpath.relative_to(self.root)
            except Exception:
                rel_path = fpath
            try:
                start_line = md.start_point[0] + 1
                end_line = md.end_point[0] + 1
            except Exception:
                start_line = end_line = -1
            self.methods[qname] = Method(str(rel_path), mname, start_line, end_line)

            body_nodes = QueryCursor(self._methods_q).captures(md).get("method-body", [])
            if not body_nodes:
                continue
            body_node = body_nodes[0]
            callees = set()
            for cnode in QueryCursor(self._calls_q).captures(body_node).get("callee", []):
                callee = cnode.text.decode()
                if callee:
                    callees.add(callee)
                    self.called_simple.add(callee)
            if mname not in self.call_graph:
                self.call_graph[mname] = set()
            self.call_graph[mname].update(callees)

    def analyze(self) -> dict:
        if not self.input_check():
            return {}

        # Roots
        project_root = self.root
        src_root = project_root / "src" / "main" / "java"
        print(src_root)
        if not src_root.exists():
            src_root = project_root

        # Seed with the method's source file
        srcfile = jpamb.sourcefile(self.method_id).relative_to(Path.cwd())
        with open(srcfile, "rb") as f:
            tree = self.parser.parse(f.read())

        queue: list[Path] = [srcfile]
        visited: set[Path] = set()
        parsed_trees: dict[Path, tree_sitter.Tree] = {srcfile: tree}

        #Imports
        while queue:
            fpath = Path(queue.pop(0))
            if fpath in visited or not fpath.exists():
                continue
            visited.add(fpath)

            if fpath in parsed_trees:
                ftree = parsed_trees[fpath]
            else:
                log.debug("parse sourcefile %s", fpath)
                with open(fpath, "rb") as fh:
                    ftree = self.parser.parse(fh.read())
                parsed_trees[fpath] = ftree

            self._extract_methods_and_calls(fpath, ftree)

            for imp in self._get_imports(ftree):
                imp_path = self._resolve_import_to_path(imp, src_root)
                if imp_path and imp_path not in visited:
                    log.debug("Following import %s -> %s", imp, imp_path)
                    queue.append(imp_path)

        all_java_files = list(project_root.rglob("*.java")) + list(project_root.rglob("*.Java"))
        for fpath in all_java_files:
            fpath = Path(fpath)
            if fpath in visited or not fpath.exists():
                continue
            visited.add(fpath)
            if fpath in parsed_trees:
                ftree = parsed_trees[fpath]
            else:
                log.debug("parse sourcefile %s", fpath)
                with open(fpath, "rb") as fh:
                    ftree = self.parser.parse(fh.read())
                parsed_trees[fpath] = ftree
            self._extract_methods_and_calls(fpath, ftree)

        method_name = self.method_id.extension.name

        reachable = self.collect_reachable(self.call_graph, [method_name])
        not_in_tree_qnames = sorted(q for q in self.all_methods_qualified if q.split(".")[-1] not in reachable)
        methods_not_in_call_tree = [self.methods[q] for q in not_in_tree_qnames if q in self.methods]

        all_methods = [self.methods[q] for q in sorted(self.methods.keys())]

        never_called_qnames = sorted(q for q in self.all_methods_qualified if q.split(".")[-1] not in self.called_simple)
        methods_never_called = [self.methods[q] for q in never_called_qnames if q in self.methods]

        return {
            "call_graph": self.call_graph,           
            "root_methods": [method_name],            
            "methods_not_in_call_tree": methods_not_in_call_tree,
            "all_methods_discovered": all_methods,
            "methods_never_called": methods_never_called,
        }

def format_call_graph_tree(call_graph: dict[str, set[str]], roots: list[str]) -> str:
    def dfs(node: str, prefix: str, path: set[str], out: list[str]):
        children = sorted(call_graph.get(node, set()))
        for i, child in enumerate(children):
            is_last = i == len(children) - 1
            connector = "└─ " if is_last else "├─ "
            if child in path:
                out.append(f"{prefix}{connector}{child} (cycle)")
                continue
            out.append(f"{prefix}{connector}{child}")
            next_prefix = prefix + ("   " if is_last else "│  ")
            dfs(child, next_prefix, path | {child}, out)

    lines: list[str] = []
    for r in roots:
        lines.append(r)
        dfs(r, "", {r}, lines)
    return "\n".join(lines)

methodid = jpamb.getmethodid(
    "syntaxer",
    "1.0",
    "Group 8",
    ["syntatic", "python"],
    for_science=True,
)

if __name__ == "__main__":
    analyzer = MethodAnalyzer(".", methodid)
    result = analyzer.analyze()
    if result:
        print("Call graph (tree):")
        print(format_call_graph_tree(result["call_graph"], result["root_methods"]))
        print("\nMethods not in call tree:")
        for m in result["methods_not_in_call_tree"]:
            print(f"  {m.methodname} [{m.file_path}:{m.start_line}-{m.end_line}]")
        print("\nAll methods discovered:")
        for m in result["all_methods_discovered"]:
            print(f"  {m.methodname} [{m.file_path}:{m.start_line}-{m.end_line}]")
        print("\nMethods never called:")
        for m in result["methods_never_called"]:
            print(f"  {m.methodname} [{m.file_path}:{m.start_line}-{m.end_line}]")



