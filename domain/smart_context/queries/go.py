"""Tree-sitter query for Go - Port từ Repomix queryGo.ts"""

QUERY = """
(comment) @comment
(package_clause) @definition.package
(import_declaration) @definition.import
(function_declaration name: (identifier) @name) @definition.function
(method_declaration name: (field_identifier) @name) @definition.method
(type_spec name: (type_identifier) @name) @definition.type
"""
