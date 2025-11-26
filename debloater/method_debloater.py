from typing import Any, Dict
from jpamb.jvm.base import AbsMethodID
import re
import os
import tree_sitter
import tree_sitter_java
from jpamb import jvm

def rename_java_class(source: str, old_name: str, new_name: str) -> str:
    """
    Rename the class declaration from old_name to new_name.
    Handles things like:
        public class Bloated {
        public final class Bloated {
        class Bloated {
    """
    pattern = re.compile(rf"(\b(?:public\s+)?(?:final\s+)?class\s+){old_name}\b")
    return pattern.sub(rf"\1{new_name}", source, count=1)

## ARGS ##

def _remove_arg_from_signature(source: str, method_name: str, arg_index: int) -> str:
    """
    Remove the arg_index-th parameter from the given method's signature.
    Only handles patterns like 'public static <ret> method(...)'.
    """
    pattern = re.compile(
        rf"(public\s+static\s+[^\s]+\s+{re.escape(method_name)}\s*)\(([^)]*)\)",
        re.MULTILINE,
    )

    def replacer(m: re.Match) -> str:
        prefix = m.group(1)
        params_str = m.group(2).strip()
        if not params_str:
            return m.group(0)  # no params

        params = [p.strip() for p in params_str.split(",") if p.strip()]
        if arg_index >= len(params):
            # index out of range -> leave as is
            return m.group(0)

        new_params = [p for i, p in enumerate(params) if i != arg_index]
        new_params_str = ", ".join(new_params)
        return f"{prefix}({new_params_str})"

    return pattern.sub(replacer, source, count=1)

import tree_sitter
import tree_sitter_java

def _remove_nth_arg_from_calls(source_code: str, method_name: str, arg_index: int) -> str:
    """
    Remove the arg_index-th argument (0-based) from all calls to `method_name`
    in this Java source file.
    """
    java_lang = tree_sitter.Language(tree_sitter_java.language())
    parser = tree_sitter.Parser(java_lang)
    source_bytes = source_code.encode("utf-8")
    tree = parser.parse(source_bytes)
    root = tree.root_node

    edits: list[tuple[int, int, bytes]] = []  # (start_byte, end_byte, replacement_bytes)

    stack = [root]
    while stack:
        node = stack.pop()
        stack.extend(reversed(node.children))

        if node.type != "method_invocation":
            continue

        name_node = node.child_by_field_name("name")
        if not name_node or not name_node.text:
            continue
        mname = name_node.text.decode()
        if mname != method_name:
            continue

        args_node = node.child_by_field_name("arguments")
        if not args_node:
            continue

        arg_exprs = list(args_node.named_children)
        if arg_index >= len(arg_exprs):
            continue

        # Build new argument text
        kept_parts: list[bytes] = []
        for i, arg_node in enumerate(arg_exprs):
            if i == arg_index:
                continue
            part = source_bytes[arg_node.start_byte:arg_node.end_byte]
            kept_parts.append(part)

        new_args_bytes = b", ".join(kept_parts)

        # replace only the inside between ( and )
        inner_start = args_node.start_byte + 1    # after '('
        inner_end = args_node.end_byte - 1    # before ')'

        edits.append((inner_start, inner_end, new_args_bytes))

    if not edits:
        return source_code

    # Apply edits from left to right
    edits.sort(key=lambda e: e[0])

    out = bytearray()
    pos = 0
    for start, end, repl in edits:
        out += source_bytes[pos:start]
        out += repl
        pos = end
    out += source_bytes[pos:]

    return out.decode("utf-8")


def remove_args_from_methods(source: str, spec: Dict[str, Any]) -> str:
    """
    Given Java source and a spec remove parameters at the given indices from each method's signature.
    """
    for method_name, data in spec.items():
        arg_indices = sorted(set(data.get("args", [])), reverse=True)
        if not arg_indices:
            continue

        for idx in arg_indices:
            # 1) remove from method signature
            source = _remove_arg_from_signature(source, method_name, idx)
            # 2) remove from all call sites
            source = _remove_nth_arg_from_calls(source, method_name, idx)

    return source

class Debloat:    
    def __init__(self, source_code: str):
        self.lines_to_be_deleted = {}       # {AbsMethodID: [lists of line numbers]}
        self.source_code = source_code
    
    def register_deletions(self, method_id: AbsMethodID, lines: list[int]):
        """
        Store deletion-line candidates for a method.
        These are NOT yet applied — this only records them.
        """
        if method_id not in self.lines_to_be_deleted.keys():
            self.lines_to_be_deleted[method_id] = []
            self.lines_to_be_deleted[method_id].append(list(lines))
        else:
            self.lines_to_be_deleted[method_id].append(list(lines))

    def sort_lines_desc(self, method_id: AbsMethodID) -> list[int]:
        """
        Sorts line numbers in descending order so they can be safely deleted
        (bottom-up deletion avoids index shifting issues).

        Returns:
            list[int]: sorted list (highest line first)
        """
        if method_id not in self.lines_to_be_deleted:
            return []

        blocks = self.lines_to_be_deleted[method_id]

        blocks = [sorted(block) for block in blocks] # sort each block's lines ascending

        blocks.sort(key=lambda b: b[0] if b else -1, reverse=True) # sort blocks by first line descending

        self.lines_to_be_deleted[method_id] = blocks

    def debloat_source(self, delete_lines: list[int]) -> str:
        """
        Deletes the specified line numbers from the source code
        and records them in self.lines_to_be_deleted[method_id].
        """
        delete_set = set(delete_lines)

        out_lines = []

        for i, line in enumerate(self.source_code.splitlines(), start=1):
            if i not in delete_set:
                out_lines.append(line)

        clean_code = "\n".join(out_lines)

        return clean_code

    def compress_blank_lines(self, code: str) -> str:
        """
        Replace multiple blank lines with a single blank line.
        """
        return re.sub(r"\n\s*\n+", "\n\n", code)

    def write_debloated_file(self, folder_path: str, class_name: str, debloated_text: str, iteration: int) -> str:
        """
        Writes the debloated Java source to a new file inside folder_path.
        """
        if not os.path.exists(folder_path):
            os.makedirs(folder_path, exist_ok=True)

        new_filename = f"{class_name}Debloated.java"
        output_path = os.path.join(folder_path, new_filename)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(debloated_text)

        return str(output_path)
    
    def apply_method_debloating(self, method_id: AbsMethodID, folder_path: str, class_name: str, iteration: int):
        """
        Apply all registered deletions for a specific method and create the debloated file.
        """
        if method_id not in self.lines_to_be_deleted:
            raise ValueError(f"No deletion lines registered for {method_id}")
        
        self.sort_lines_desc(method_id) # sort lines for safe deletion
        blocks = self.lines_to_be_deleted[method_id] # get lines to delete
        sum_blocks = sum(blocks, []) # flatten list of lists
        new_source = self.debloat_source(sum_blocks) # debloat source
        self.write_debloated_file(folder_path, class_name, new_source, iteration) # write debloated file
        
        
    def debloat_from_spec(
        self,
        spec: dict,
        folder_path: str,
        class_name: str,
        iteration: int,
        not_called_methods: list[str] = None
    ) -> str:
        """
        spec: {
          "methodName": {
              "lines": [ ... ],
              "args": [ ... ]
          },
          ...
        }
        not_called_methods: [method_id_as_str]
        """
        # 1) Collect ALL line numbers to delete across all methods
        all_lines_to_delete: set[int] = set()
        for method_name, info in spec.items():
            lines = info.get("lines", [])
            if lines:
                self.register_deletions(method_name, lines)
                all_lines_to_delete.update(lines)

        # 2) Delete those lines from the source once (line numbers refer to original file)
        debloated = self.debloat_source(sorted(all_lines_to_delete))

        # 3) Remove unused arguments from method signatures based on spec["..."]["args"]
        debloated = remove_args_from_methods(debloated, spec)
        
        # 4) Remove unreachable methods if exists
        if not_called_methods is not None:
            self.remove_methods_by_name(not_called_methods)
        
        # 5) Rename class, because classname should be = to filename
        new_class_name = class_name + "Debloated"
        debloated = rename_java_class(debloated, class_name, new_class_name)

        # 6) Clean up extra blank lines
        debloated = self.compress_blank_lines(debloated)

        # 7) Write out the new debloated file
        output_path = self.write_debloated_file(folder_path, class_name, debloated, iteration)
        return output_path
    
    def remove_methods_by_name(self, method_names: list[str]) -> str:
        # 1) Parse Java source
        print(method_names)
        
        m_names = list()
        
        for m in method_names:
            m_id = jvm.AbsMethodID.decode(m)
            m_names.append(m_id.extension.name)
        
        java_lang = tree_sitter.Language(tree_sitter_java.language())
        parser = tree_sitter.Parser(java_lang)
        tree = parser.parse(self.source_code.encode("utf-8"))
        root = tree.root_node

        target = set(m_names)
        lines_to_delete: set[int] = set()

        # 2) Walk the tree and find method_declaration nodes
        stack = [root]
        while stack:
            node = stack.pop()
            # Push children for DFS
            stack.extend(reversed(node.children))

            if node.type != "method_declaration":
                continue

            # 3) Get the method name
            name_node = node.child_by_field_name("name")
            
            print(f"FOUND: {name_node.text}")
            
            if not name_node or not name_node.text:
                continue
            mname = name_node.text.decode()

            if mname not in target:
                continue

            # 4) Convert node's start/end points to 1-based line numbers
            start_line = node.start_point[0] + 1  # tree-sitter is 0-based
            end_line = node.end_point[0] + 1

            for ln in range(start_line, end_line + 1):
                lines_to_delete.add(ln)


        print(lines_to_delete)
        # 5) Delete all those lines in a single pass
        new_source = self.debloat_source(sorted(lines_to_delete))
        new_source = self.compress_blank_lines(new_source)
        return new_source
    

