import json
import sys
from loguru import logger

from debloater.method_debloater import Debloat
from debloater.static.abstract_interpreter import static_bytecode_analysis

logger.remove()
logger.add(sys.stderr, format="[{level}] {message}", level="DEBUG")

def main_analysis(execute = False):
    logger.info(f"Running CFG builder - looking for unreferenced functions:")
    # called, not_called = cfg(root)

    called = [
    "jpamb.cases.Bloated.unreachableBranchBasic:(I)I",
    "jpamb.cases.Bloated.localInitButNotUsed:()I",
    "jpamb.cases.Bloated.unreachableBranchFor:(I)I",
    "jpamb.cases.Bloated.unreachableBranchWhile:(I)I",
    "jpamb.cases.Bloated.unreachableBranchArray:(I)I",
    "jpamb.cases.Bloated.deadArg:(I)I",
    "jpamb.cases.Bloated.unreachableBranchBasicFloat:(F)F",
    "jpamb.cases.Bloated.deadLocalInitialization:(I)I",
    "jpamb.cases.Bloated.unreachableLoopBranchOnIndex:()V",
    "jpamb.cases.Bloated.unreachableArrayOutOfBounds:()V",
    "jpamb.cases.Bloated.unreachableDivideByZeroBranch:()I",
]
    logger.info(f"Running static analyzer - looking for dead code inside functions:")
    json_per_function = static_bytecode_analysis(called)

    if execute:
         # Debloating -> java source files
        with open("src/main/java/jpamb/cases/Bloated.java", "r", encoding="utf-8") as f:
            source_code = f.read()
        
        debloater = Debloat(source_code)
        output_path = debloater.debloat_from_spec(
            json_per_function,
            folder_path="src/main/java/jpamb/cases",
            class_name="Bloated",
            iteration=0,
        )

        print("Debloated file written to:", output_path)
        
        # Dynamic -> 
    

main_analysis(execute=True)
