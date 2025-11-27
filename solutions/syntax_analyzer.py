#!/usr/bin/env python3
import logging
import jpamb
import sys

from syntax_analyzers.call_graph import CallGraphBuilder
from syntax_analyzers.input_generator import RandomInputGenerator
from syntax_analyzers.z3_input_generator import Z3InputGenerator

log = logging
log.basicConfig(level=logging.DEBUG)


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
    input_generator = Z3InputGenerator(methodid)
    fuzz_result = input_generator.analyze()
    if not fuzz_result:
        sys.exit(1)
    else:
        print(fuzz_result)

    analyzer = CallGraphBuilder(".", methodid)
    call_graph_result = analyzer.analyze()
    if False:
        call_graph = call_graph_result["call_graph"]
        reachable = analyzer.collect_reachable(call_graph, call_graph_result["root_methods"])

        print("Methods in call graph (reachable from roots):")
        for name in sorted(reachable):
            print(f"  {name}")
        print("Call graph (tree):")
        print(format_call_graph_tree(call_graph_result["call_graph"], call_graph_result["root_methods"]))
        print("\nMethods not in call tree:")
        for m in call_graph_result["methods_not_in_call_tree"]:
            print(f"  {m.methodname} [{m.file_path}:{m.start_line}-{m.end_line}]")
        print("\nAll methods discovered:")
        for m in call_graph_result["all_methods_discovered"]:
            print(f"  {m.methodname} [{m.file_path}:{m.start_line}-{m.end_line}]")
        print("\nMethods never called:")
        for m in call_graph_result["methods_never_called"]:
            print(f"  {m.methodname} [{m.file_path}:{m.start_line}-{m.end_line}]")
    else:
        log.warning("call graph analysis returned no data")



