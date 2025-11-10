import json
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Set

# --- CFG Block ---
@dataclass
class Block:
    id: int
    statements: List[str]
    successors: List[int]
    reachable: bool = False

# --- Build CFG from JSON method ---
def build_cfg_from_json_method(method_json) -> Dict[int, Block]:
    bytecode = method_json["code"]["bytecode"]
    blocks: Dict[int, Block] = {}
    offset_to_block: Dict[int, int] = {}

    # find jump targets
    jump_targets = {instr.get("target") for instr in bytecode if "target" in instr}
    all_offsets = {instr["offset"] for instr in bytecode} | jump_targets

    # create a block for each offset
    for offset in sorted(all_offsets):
        if offset not in offset_to_block:
            block_id = len(blocks)
            offset_to_block[offset] = block_id
            blocks[block_id] = Block(block_id, [], [])

    # assign statements and successors
    for i, instr in enumerate(bytecode):
        offset = instr["offset"]
        block_id = offset_to_block[offset]
        block = blocks[block_id]
        block.statements.append(str(instr))

        # determine successors
        if instr["opr"] in ["goto", "ifz", "ifnz", "if_icmpeq", "if_icmpne"]:
            target_offset = instr.get("target")
            if target_offset is not None:
                block.successors.append(offset_to_block[target_offset])
            if instr["opr"].startswith("if") and i + 1 < len(bytecode):
                next_offset = bytecode[i + 1]["offset"]
                block.successors.append(offset_to_block[next_offset])
        elif instr["opr"] == "return":
            block.successors = []
        else:
            if i + 1 < len(bytecode):
                next_offset = bytecode[i + 1]["offset"]
                if offset_to_block[next_offset] not in block.successors:
                    block.successors.append(offset_to_block[next_offset])

    return blocks

# --- Analyze CFG for reachability ---
def analyze_cfg(blocks: Dict[int, Block]):
    worklist = [0]
    blocks[0].reachable = True

    while worklist:
        b_id = worklist.pop()
        block = blocks[b_id]
        for succ_id in block.successors:
            succ = blocks[succ_id]
            if not succ.reachable:
                succ.reachable = True
                worklist.append(succ_id)
    return blocks

# --- Remove unreachable lines ---
def remove_unreachable_lines(method_json, blocks):
    bytecode = method_json["code"]["bytecode"]
    reachable_stmts = {stmt for block in blocks.values() if block.reachable for stmt in block.statements}
    method_json["code"]["bytecode"] = [instr for instr in bytecode if str(instr) in reachable_stmts]
    return method_json

# --- Print CFG ---
def print_cfg(blocks: Dict[int, Block]):
    print("CFG:")
    for b in blocks.values():
        succs = ", ".join(str(s) for s in b.successors)
        status = "reachable" if b.reachable else "unreachable"
        print(f"Block {b.id}: statements={b.statements}, successors=[{succs}], {status}")
    print("---")

# --- Debloat a JSON file ---
def debloat_file(json_path: str):
    with open(json_path) as f:
        data = json.load(f)

    for method in data["methods"]:
        if "code" not in method:
            continue

        # Build and analyze CFG
        cfg = build_cfg_from_json_method(method)
        cfg = analyze_cfg(cfg)

        # Print CFG after analysis
        print(f"\nMethod: {method['name']}")
        print_cfg(cfg)

        # Remove unreachable instructions
        remove_unreachable_lines(method, cfg)

    output_path = Path(json_path).with_name(Path(json_path).stem + "_debloated.json")
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"✅ Debloated file saved as: {output_path}")
    return output_path

# --- Report removed instructions ---
def report_removal(original_path, debloated_path):
    with open(original_path) as f:
        original = json.load(f)
    with open(debloated_path) as f:
        debloated = json.load(f)

    total_orig = sum(len(m.get("code", {}).get("bytecode", [])) for m in original["methods"])
    total_debloated = sum(len(m.get("code", {}).get("bytecode", [])) for m in debloated["methods"])
    removed = total_orig - total_debloated
    percent = (removed / total_orig * 100) if total_orig else 0

    print(f"\nTotal instructions removed: {removed}/{total_orig} ({percent:.1f}%)")

    # Per-method removal
    for orig_method, deb_method in zip(original["methods"], debloated["methods"]):
        orig_bc = orig_method.get("code", {}).get("bytecode", [])
        deb_bc = deb_method.get("code", {}).get("bytecode", [])
        removed_bc = [instr for instr in orig_bc if instr not in deb_bc]
        print(f"Method: {orig_method['name']} - Removed {len(removed_bc)} instructions")

# --- Main ---
if __name__ == "__main__":
    original_path = "/home/udimitra/jpamb/solutions/mini_test.json"
    debloated_path = debloat_file(original_path)
    report_removal(original_path, debloated_path)
