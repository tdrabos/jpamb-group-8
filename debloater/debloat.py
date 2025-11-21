from jpamb.jvm.base import AbsMethodID
import re
import os

class Debloat:
    def __init__(self, source_code: str):
        self.lines_deleted = {}       # {AbsMethodID: [line numbers]}
        self.source_code = source_code

    def debloat_source(self, delete_lines: list[int], method_id: AbsMethodID) -> str:
        """
        Deletes the specified line numbers from the source code
        and records them in self.lines_deleted[method_id].
        """

        delete_set = set(delete_lines)

        # track deleted lines
        if method_id not in self.lines_deleted:
            self.lines_deleted[method_id] = []
        self.lines_deleted[method_id].extend(sorted(delete_lines))

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