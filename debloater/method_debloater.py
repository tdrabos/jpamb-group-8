from typing import Any, Dict
from jpamb.jvm.base import AbsMethodID
import re
import os

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

def remove_args_from_methods(source: str, spec: Dict[str, Any]) -> str:
    """
    Given Java source and a spec of the form:
      { "methodName": { "lines": [...], "args": [indices...] }, ... }
    remove parameters at the given indices from each method's *signature*.
    """
    for method_name, data in spec.items():
        arg_indices = set(data.get("args", []))
        if not arg_indices:
            continue  # nothing to remove for this method

        # Simplified pattern: matches e.g.
        #   public static int deadArg(int n) {
        #   public static void unreachableLoopBranchOnIndex() {
        #
        # group(1): "public static int deadArg"
        # group(2): "int n"  (or empty)
        pattern = re.compile(
            rf"(public\s+static\s+[^\s]+\s+{re.escape(method_name)}\s*)\(([^)]*)\)",
            re.MULTILINE,
        )

        def replacer(m: re.Match) -> str:
            prefix = m.group(1)
            params_str = m.group(2).strip()
            if not params_str:
                # No params to begin with
                return m.group(0)

            # Split params by comma, keep order
            params = [p.strip() for p in params_str.split(",") if p.strip()]
            # Remove the ones whose indices appear in arg_indices (0-based)
            new_params = [p for i, p in enumerate(params) if i not in arg_indices]
            new_params_str = ", ".join(new_params)
            return f"{prefix}({new_params_str})"

        # Apply once per method (assuming one declaration per file)
        source = pattern.sub(replacer, source, count=1)

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
        
        
    def debloat_from_spec(self, spec: dict, folder_path: str, class_name: str, iteration: int) -> str:
        """
        spec: {
          "methodName": {
              "lines": [ ... ],
              "args": [ ... ]
          },
          ...
        }
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
        
        # 4) Rename class, because classname should be = to filename
        new_class_name = class_name + "Debloated"
        debloated = rename_java_class(debloated, class_name, new_class_name)

        # 5) Clean up extra blank lines
        debloated = self.compress_blank_lines(debloated)

        # 6) Write out the new debloated file
        output_path = self.write_debloated_file(folder_path, class_name, debloated, iteration)
        return output_path
    

