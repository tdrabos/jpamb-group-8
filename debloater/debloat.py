import json
import sys
from loguru import logger

from debloater.method_debloater import Debloat
from debloater.static.abstract_interpreter import static_bytecode_analysis
from debloater.syntax_analyzer import cfg
from jpamb.jvm.base import AbsMethodID

logger.remove()
logger.add(sys.stderr, format="[{level}] {message}", level="DEBUG")

def main_analysis(execute = True, from_main=False):
    if from_main:
        logger.info(f"Running CFG builder - looking for unreferenced functions:")
        called, not_called = cfg(AbsMethodID.decode("jpamb.cases.BloatedMain.main:()I"), "BloatedMain")
    else:
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
        not_called = None
    
    cname = "BloatedMain" if from_main else "Bloated"

    logger.info(f"Running static analyzer - looking for dead code inside functions:")
    json_per_function = static_bytecode_analysis(called, f"target/decompiled/jpamb/cases/{cname}.json")

    if execute:
        # Debloating -> java source files            
        with open(f"src/main/java/jpamb/cases/{cname}.java", "r", encoding="utf-8") as f:
            source_code = f.read()
        
        debloater = Debloat(source_code)
        output_path = debloater.debloat_from_spec(
            json_per_function,
            folder_path="src/main/java/jpamb/cases",
            class_name=cname,
            iteration=0,
            not_called_methods=not_called
        )
        

        print("Debloated file written to:", output_path)
        
        # Dynamic
    

main_analysis(from_main=True)
