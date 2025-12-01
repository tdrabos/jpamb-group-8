import json
from typing import Tuple
from debloater.syntactic.call_graph_builder import call_graph
from jpamb.jvm.base import AbsMethodID
from debloater.dynamic_analyzer import run, run_coverage
from jpamb.jvm.base import AbsMethodID
from debloater.syntactic.combined_input_generator import generate_inputs

def build_pairs():

    called_original, _ = call_graph(AbsMethodID.decode("jpamb.cases.BloatedMain.main:()I"), "BloatedMain")
    called_debloated, _ = call_graph(AbsMethodID.decode("jpamb.cases.BloatedMainDebloated.main:()I"), "BloatedMainDebloated")
        
    def method_name(m: str) -> str:
        return AbsMethodID.decode(m).extension.name

    # Build lookup from debloated methods by method name
    debloated_by_name = {method_name(s): s for s in called_debloated}

    # Create pairs (original, debloated) where names match
    pairs = [
        (orig, debloated_by_name[name])
        for orig in called_original
        if (name := method_name(orig)) in debloated_by_name
    ]
    
    return pairs
    
def output_check():
    pairs = build_pairs()
    
    results: dict[str, any] = dict()

    for m_o, m_d in pairs:
        print(f"Pair: {m_o} ; {m_d}")
        
        o_id = AbsMethodID.decode(m_o)
        d_id = AbsMethodID.decode(m_d)
        
        inputs_dict = generate_inputs([m_d], 2)
        for i in inputs_dict.values():
            inputs = [x[0] for x in i if x]
            print(inputs_dict)
            print(inputs)
            if len(inputs) > 0:
                for inp in inputs:
                    out_original = run(o_id, inputs)
                    out_debloated = run(d_id, inputs)
                
                    results[f"{o_id.extension.name}_{inp}"] = (out_original, out_debloated, out_original == out_debloated)
            else:
                out_original = run(o_id, inputs)
                out_debloated = run(d_id, inputs)
                
                results[f"{o_id.extension.name}"] = (out_original, out_debloated, out_original == out_debloated)
    return results
        
def coverage_percent():
    pairs = build_pairs()
    
    results: dict[str, Tuple[str, str]] = dict()
    
    for m_o, m_d in pairs:
        print(f"Pair: {m_o} ; {m_d}")
        
        o_id = AbsMethodID.decode(m_o)
        d_id = AbsMethodID.decode(m_d)
        
        original_cov = run_coverage(o_id)
        debloated_cov = run_coverage(d_id)
        
        results[o_id.extension.name] = (f"{original_cov}%", f"{debloated_cov}%")
        
    return results
            
print(json.dumps(output_check(), indent=4))
print(json.dumps(coverage_percent(), indent=4))