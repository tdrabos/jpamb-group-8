from jpamb.jvm.base import AbsMethodID
import re
import os

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

        new_filename = f"{class_name}_debloated_{iteration}.java"
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