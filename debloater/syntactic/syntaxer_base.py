from abc import ABC, abstractmethod
import tree_sitter
import jpamb
from pathlib import Path
from tree_sitter import Query, QueryCursor
import logging

log = logging
log.basicConfig(level=logging.DEBUG)

class QueryRegistry:
    JAVA_LANGUAGE = tree_sitter.Language(
        __import__('tree_sitter_java').language()
    )

    @staticmethod
    def class_query(simple_classname: str) -> Query:
        return Query(
            QueryRegistry.JAVA_LANGUAGE,
            f"""
            (class_declaration 
                name: ((identifier) @class-name 
                      (#eq? @class-name "{simple_classname}"))) @class
            """,
        )

    @staticmethod
    def method_query(method_name: str) -> Query:
        return Query(
            QueryRegistry.JAVA_LANGUAGE,
            f"""
            (method_declaration 
                name: ((identifier) @method-name 
                      (#eq? @method-name "{method_name}"))
            ) @method
            """,
        )

    @staticmethod
    def methods_query() -> Query:
        return Query(
            QueryRegistry.JAVA_LANGUAGE,
            """
            (method_declaration
                name: (identifier) @method-name
                body: (block) @method-body) @method
            """
        )

    @staticmethod
    def calls_query() -> Query:
        return Query(
            QueryRegistry.JAVA_LANGUAGE,
            """
            (method_invocation
                name: (identifier) @callee)
            """
        )
    
    @staticmethod
    def import_query() -> Query:
        return Query(
            QueryRegistry.JAVA_LANGUAGE,
            """
            (import_declaration
                (scoped_identifier) @import-name)
            """
        )

    @staticmethod
    def conditions_query() -> Query:
        return Query(
            QueryRegistry.JAVA_LANGUAGE,
            """
            (if_statement condition: (_) @condition)
            (while_statement condition: (parenthesized_expression (_) @condition))
            (for_statement condition: (_) @condition)
            """
        )

    @staticmethod
    def package_query() -> Query:
        return Query(
            QueryRegistry.JAVA_LANGUAGE,
            """
            (package_declaration
                (scoped_identifier) @package-name)
            """
        )

class Method:
    # Store method metadata
    def __init__(
        self,
        file_path: str,
        class_name: str,
        methodname: str,
        start_line: int,
        end_line: int,
        descriptor: str | None = None,
    ):
        self.file_path = file_path
        self.class_name = class_name
        self.methodname = methodname
        self.start_line = start_line
        self.end_line = end_line
        self.descriptor = descriptor

class BaseSyntaxer(ABC):
    def __init__(self, method_id: jpamb.jvm.base.AbsMethodID):
        self.parser = tree_sitter.Parser(QueryRegistry.JAVA_LANGUAGE)
        self.method_id = method_id

    def input_check(self) -> bool:
        srcfile = jpamb.sourcefile(self.method_id).relative_to(Path.cwd())
        with open(srcfile, "rb") as f:
            #log.debug("parse sourcefile %s", srcfile)
            tree = self.parser.parse(f.read())
        simple_classname = str(self.method_id.classname.name)

        class_nodes = QueryCursor(QueryRegistry.class_query(simple_classname)).captures(tree.root_node).get("class", [])
        if not class_nodes:
            log.error(f"could not find a class of name {simple_classname} in {srcfile}")
            return False

        method_name = self.method_id.extension.name
        for cls in class_nodes:
            for node in QueryCursor(QueryRegistry.method_query(method_name)).captures(cls).get("method", []):
                p = node.child_by_field_name("parameters")
                if not p:
                    continue
                params = [c for c in p.children if c.type == "formal_parameter"]
                if len(params) != len(self.method_id.extension.params):
                    continue
                return True

        log.warning(f"could not find a method of name {method_name} in {simple_classname}")
        return False
    
    @abstractmethod
    def analyze(self):
        pass
