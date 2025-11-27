from pathlib import Path
import tree_sitter
from tree_sitter import QueryCursor
import logging
from .base import BaseSyntaxer, QueryRegistry, Method
import jpamb

log = logging
log.basicConfig(level=logging.DEBUG)

class CallGraphBuilder(BaseSyntaxer):
    def __init__(self, root: str, method_id: jpamb.jvm.base.AbsMethodID):
        super().__init__(method_id)
        self.root = Path(root).resolve()
        self.call_graph: dict[str, set[str]] = {}
        self.all_methods_qualified: set[str] = set()
        self.called_simple: set[str] = set()
        self.methods: dict[str, Method] = {}
        self._methods_q = QueryRegistry.methods_query()
        self._calls_q = QueryRegistry.calls_query()

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

        project_root = self.root
        src_root = project_root / "src" / "main" / "java"
        if not src_root.exists():
            src_root = project_root

        srcfile = jpamb.sourcefile(self.method_id).relative_to(Path.cwd())
        with open(srcfile, "rb") as f:
            tree = self.parser.parse(f.read())

        queue: list[Path] = [srcfile]
        visited: set[Path] = set()
        parsed_trees: dict[Path, tree_sitter.Tree] = {srcfile: tree}

        while queue:
            fpath = Path(queue.pop(0))
            if fpath in visited or not fpath.exists():
                continue
            visited.add(fpath)

            if fpath in parsed_trees:
                ftree = parsed_trees[fpath]
            else:
                with open(fpath, "rb") as fh:
                    ftree = self.parser.parse(fh.read())
                parsed_trees[fpath] = ftree

            self._extract_methods_and_calls(fpath, ftree)

            for imp in self._get_imports(ftree):
                imp_path = self._resolve_import_to_path(imp, src_root)
                if imp_path and imp_path not in visited:
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
