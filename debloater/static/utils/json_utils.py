from typing import Iterable, Dict, List, Optional, Set


def _build_offset_to_line(lines_table: list[dict]) -> callable:
    entries = sorted(lines_table, key=lambda e: e["offset"])

    def offset_to_lines(offset: int) -> Set[int]:
        if not entries:
            return set()

        prev_idx: Optional[int] = None

        for i, entry in enumerate(entries):
            if entry["offset"] <= offset:
                prev_idx = i
            else:
                break

        if prev_idx is None:
            # offset before first mapping: no line info
            return set()

        cur_line = entries[prev_idx]["line"]
    
        if prev_idx + 1 < len(entries):
            next_line = entries[prev_idx + 1]["line"]
            if next_line > cur_line:
                return set(range(cur_line, next_line))
        
        return {cur_line}

    return offset_to_lines


def dead_indices_to_lines_for_method(method_json: dict, dead_indices: Iterable[int]) -> List[int]:
    """
    Given a single method JSON object (one element from class_json["methods"])
    and a collection of bytecode indices that are dead, return the sorted
    list of source lines corresponding to those indices.
    """
    code = method_json.get("code")
    if not code:
        return []

    bytecode = code.get("bytecode", [])
    offset_to_line = _build_offset_to_line(code.get("lines", []))

    dead_lines: Set[int] = set()

    for idx in dead_indices:
        if 0 <= idx < len(bytecode):
            lines = offset_to_line(idx)
            if lines is not None:
                dead_lines |= lines

    return sorted(dead_lines)


def dead_indices_to_lines_in_class(
    class_json: dict,
    dead_indices_by_method: Dict[str, Iterable[int]],
    dead_args: Dict[str, Iterable[int]]
) -> Dict[str, Dict[str, Iterable[int]]]:
    """
    For the whole class JSON, map each method name to the list of line numbers
    that correspond to its dead bytecode indices.
    """
    result: Dict[str, List[int]] = {}
    
    print(dead_args)

    for m in class_json.get("methods", []):
        name = m["name"]
        if name not in dead_indices_by_method:
            continue
        dead_indices = dead_indices_by_method[name]
        
        lines = dead_indices_to_lines_for_method(m, dead_indices)
        result[name] = dict()
        result[name]["lines"] = lines
    

    return result
