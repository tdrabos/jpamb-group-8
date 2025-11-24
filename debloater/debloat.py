import sys
from loguru import logger

from debloater.static.abstract_interpreter import static_bytecode_analysis

logger.remove()
logger.add(sys.stderr, format="[{level}] {message}", level="DEBUG")

def main_analysis():
    logger.info(f"Running CFG builder - looking for unreferenced functions:")
    # called, not_called = cfg(root)

    called = [
        "jpamb.cases.Bloated.unreachableBranchBasic:(I)I",
        "jpamb.cases.Bloated.unreachableBranchFor:(I)I",
        "jpamb.cases.Bloated.unreachableBranchWhile:(I)I",
        "jpamb.cases.Bloated.unreachableBranchArray:(I)I",
        "jpamb.cases.Bloated.deadArg:(I)I",
        "jpamb.cases.Bloated.deadStore:()I",
        #"jpamb.cases.Bloated.keepObservableArrayWrite:(I)V",
        "jpamb.cases.Bloated.unreachableBranchBasicFloat:(F)F"
    ]
    logger.info(f"Running static analyzer - looking for dead code inside functions:")
    json_per_function = static_bytecode_analysis(called)
    print(json_per_function)
    
    # Debloating -> java source files
    
    # Dynamic -> 
    

main_analysis()
