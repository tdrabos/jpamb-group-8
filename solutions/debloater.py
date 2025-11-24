import json
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Set, Optional

# --- CFG Block ---
@dataclass
class Block:
    id: int
    statements: List[str]
    successors: List[int]
    reachable: bool = False

# --- SignSet for abstract interpretation ---
Sign = str  # "+", "-", "0"
@dataclass
class SignSet:
    signs: Set[Sign]

    @classmethod
    def abstract(cls, values: List[int]) -> "SignSet":
        s = set()
        for v in values:
            if v > 0:
                s.add("+")
            elif v < 0:
                s.add("-")
            else:
                s.add("0")
        return cls(s)

# --- Build CFG from JSON method ---
def build_cfg_from_json_method(method_json) -> Dict[int, Block]:
    bytecode = method_json["code"]["bytecode"]
    blocks: Dict[int, Block] = {}
    offset_to_block: Dict[int, int] = {}

    jump_targets = {instr.get("target") for instr in bytecode if "target" in instr}
    all_offsets = {instr["offset"] for instr in bytecode} | jump_targets

    for offset in sorted(all_offsets):
        if offset not in offset_to_block:
            block_id = len(blocks)
            offset_to_block[offset] = block_id
            blocks[block_id] = Block(block_id, [], [])

    for i, instr in enumerate(bytecode):
        offset = instr["offset"]
        block_id = offset_to_block[offset]
        block = blocks[block_id]
        block.statements.append(str(instr))

        if instr["opr"] in ["goto", "ifz", "ifnz", "if_icmpeq", "if_icmpne"]:
            target_offset = instr.get("target")
            if target_offset is not None:
                block.successors.append(offset_to_block[target_offset])
            if instr["opr"].startswith("if"):
                if i + 1 < len(bytecode):
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
def analyze_cfg(blocks: Dict[int, Block], x_value: int = 0):
    from copy import deepcopy
    blocks = deepcopy(blocks)
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
    reachable_stmts = set()
    for block in blocks.values():
        if block.reachable:
            reachable_stmts.update(block.statements)
    new_bytecode = [instr for instr in bytecode if str(instr) in reachable_stmts]
    method_json["code"]["bytecode"] = new_bytecode
    return method_json

# --- Debloat file ---
def debloat_file(json_path):
    with open(json_path) as f:
        data = json.load(f)

    for method in data["methods"]:
        if "code" not in method:
            continue
        cfg = build_cfg_from_json_method(method)
        cfg = analyze_cfg(cfg)
        remove_unreachable_lines(method, cfg)

    output_path = Path(json_path).with_name(Path(json_path).stem + "_debloated.json")
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"✅ Debloated file saved as: {output_path}")



with open("/home/udimitra/jpamb/decompiled/jpamb/cases/Simple.json") as f:
    original = json.load(f)

with open("/home/udimitra/jpamb/decompiled/jpamb/cases/Simple_debloated.json") as f:
    debloated = json.load(f)

# Compare bytecode per method
for orig_method, deb_method in zip(original["methods"], debloated["methods"]):
    orig_bc = orig_method["code"]["bytecode"]
    deb_bc = deb_method["code"]["bytecode"]

    removed = [instr for instr in orig_bc if instr not in deb_bc]
    print(f"Method: {orig_method['name']}")
    print(f"Removed instructions ({len(removed)}):")
    for instr in removed:
        print(instr)
    print("---")



if __name__ == "__main__":
    original_path = "/home/udimitra/jpamb/decompiled/jpamb/cases/Simple.json"
    
    # Load original
    with open(original_path) as f:
        original = json.load(f)

    # Debloat
    debloat_file(original_path)

    # Load debloated
    debloated_path = str(Path(original_path).with_name(Path(original_path).stem + "_debloated.json"))
    with open(debloated_path) as f:
        debloated = json.load(f)

    # Calculate percentage removed
    original_count = sum(len(m["code"]["bytecode"]) for m in original["methods"])
    debloated_count = sum(len(m["code"]["bytecode"]) for m in debloated["methods"])
    removed_count = original_count - debloated_count
    percent_removed = (removed_count / original_count * 100) if original_count else 0

    print(f"Total instructions removed: {removed_count}/{original_count} ({percent_removed:.1f}%)")
