"""Tree-sitter query for C++ - Port từ Repomix queryCpp.ts"""

QUERY = """
(comment) @comment
(struct_specifier name: (type_identifier) @name.definition.class) @definition.class
(class_specifier name: (type_identifier) @name.definition.class) @definition.class
(function_declarator declarator: (identifier) @name.definition.function) @definition.function
(type_definition declarator: (type_identifier) @name.definition.type) @definition.type
(enum_specifier name: (type_identifier) @name.definition.type) @definition.type
"""
