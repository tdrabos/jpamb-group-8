#!/usr/bin/env python3
import logging
from jpamb.jvm.base import AbsMethodID
import tree_sitter
import jpamb
from pathlib import Path
from tree_sitter import QueryCursor
#from syntaxer_base import BaseSyntaxer, QueryRegistry, Method
from .syntaxer_base import BaseSyntaxer, QueryRegistry, Method

# TODO: Expected output of this whole thing:
# A list of Method ID STRINGS, which are in the following format:
# "jpamb.cases.Bloated.unreachableBranchBasic:(I)I"
# For reference: check debloat.py, because I have the input of my static analyzer as the "called" array there. That is the format i need

log = logging
log.basicConfig(level=logging.DEBUG)


class CallGraphBuilder(BaseSyntaxer):
    def __init__(self, root: str, method_id: AbsMethodID, target_class: str):
        super().__init__(method_id)
        self.root = Path(root).resolve()
        self.call_graph: dict[str, set[str]] = {}
        self.all_methods_qualified: set[str] = set()
        self.called_simple: set[str] = set()
        self.methods: dict[str, Method] = {}
        self._methods_q = QueryRegistry.methods_query()
        self._calls_q = QueryRegistry.calls_query()
        
        self.target_class_simple = target_class

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
        package_name = self._get_package_name(ftree)
        
        for md in QueryCursor(self._methods_q).captures(ftree.root_node).get("method", []):
            name_nodes = QueryCursor(self._methods_q).captures(md).get("method-name", [])
            if not name_nodes:
                continue
            mname = name_nodes[0].text.decode()

            cname = self._enclosing_class_name(md)
            if not cname:
                continue

            # Only keep methods in the target class (simple name)
            if self.target_class_simple and cname != self.target_class_simple:
                continue

            # Fully-qualified class name, e.g. "jpamb.cases.Bloated"
            fqcn = f"{package_name}.{cname}" if package_name else cname
            qname = f"{fqcn}.{mname}"
            
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

            descriptor = self._method_descriptor(md)

            self.methods[qname] = Method(
                file_path=str(rel_path),
                class_name=fqcn, # store FQ class name
                methodname=mname,
                start_line=start_line,
                end_line=end_line,
                descriptor=descriptor, # store descriptor
            )

            # Collect callees (simple names)
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
            
    def method_id_strings_for_target_class(self, result: dict, target_class: str) -> list[str]:
        methods: list[Method] = result["all_methods_discovered"]
        ids: list[str] = []

        for m in methods:
            # simple name must match the target class
            if m.class_name.split(".")[-1] != target_class:
                continue
            if not m.descriptor:
                continue
            if m.methodname == "main":
                continue
            ids.append(f"{m.class_name}.{m.methodname}:{m.descriptor}")

        return sorted(ids)

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
        
    def method_id_strings_never_called_in_target(
        self,
        result: dict,
        target_class: str
    ) -> list[str]:
        methods_never_called: list[Method] = result.get("methods_never_called", [])
        ids: list[str] = []

        for m in methods_never_called:
            if m.class_name.split(".")[-1] != target_class:
                continue

            if not m.descriptor:
                continue
            if m.methodname == "main":
                continue

            ids.append(f"{m.class_name}.{m.methodname}:{m.descriptor}")

        return sorted(ids)
        
    def _get_package_name(self, t: tree_sitter.Tree) -> str | None:
        """
        Return the package name of the compilation unit, e.g. 'jpamb.cases',
        or None if there is no package declaration.
        """
        q = QueryRegistry.package_query()
        for node in QueryCursor(q).captures(t.root_node).get("package-name", []):
            return node.text.decode()
        return None

    def _java_type_to_descriptor(self, t: str) -> str:
        """
        Map a Java type string to a JVM descriptor fragment.
        Handles primitives and simple arrays like 'int', 'float', 'int[]', 'float[]', etc.
        """
        t = t.strip()
        # Handle arrays: int[] -> [I, etc.
        dims = 0
        while t.endswith("[]"):
            dims += 1
            t = t[:-2].strip()

        prim = {
            "boolean": "Z",
            "byte":    "B",
            "char":    "C",
            "short":   "S",
            "int":     "I",
            "long":    "J",
            "float":   "F",
            "double":  "D",
            "void":    "V",
        }

        if t in prim:
            base = prim[t]
        else:
            # Object type, best-effort: Lpkg/Class;
            base = "L" + t.replace(".", "/") + ";"

        desc = base
        for _ in range(dims):
            desc = "[" + desc
        return desc

    def _method_descriptor(self, md: tree_sitter.Node) -> str:
        """
        Compute a JVM method descriptor from a method_declaration node.
        Example: '(I)I', '()V', '(F)F', etc.
        """
        # Parameters
        params_node = md.child_by_field_name("parameters")
        param_descs: list[str] = []
        if params_node:
            for ch in params_node.children:
                if ch.type != "formal_parameter":
                    continue
                type_node = ch.child_by_field_name("type")
                if not type_node:
                    continue
                type_text = type_node.text.decode()
                param_descs.append(self._java_type_to_descriptor(type_text))

        # Return type
        rt_node = md.child_by_field_name("type")
        if rt_node is not None:
            rt_text = rt_node.text.decode()
            rt_desc = self._java_type_to_descriptor(rt_text)
        else:
            # treat as void
            rt_desc = "V"

        return "(" + "".join(param_descs) + ")" + rt_desc

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

def call_graph(main_method_id: AbsMethodID, class_name: str):
    analyzer = CallGraphBuilder("src/main/java/jpamb/cases", method_id=main_method_id, target_class=class_name)
    result = analyzer.analyze()
    if not result:
        log.error(f"Failed to construct CFG for {class_name} main method")
    # Produce the "called" array in the required string format
    all_m = analyzer.method_id_strings_for_target_class(result, class_name)
    not_called = analyzer.method_id_strings_never_called_in_target(result, class_name)
    
    called = list(set(all_m) - set(not_called))
    
    return called, not_called




