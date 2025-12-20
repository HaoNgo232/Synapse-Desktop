"""Tree-sitter query for C# - Port từ Repomix queryCSharp.ts"""

QUERY = """
(comment) @comment
(class_declaration name: (identifier) @name.definition.class) @definition.class
(interface_declaration name: (identifier) @name.definition.interface) @definition.interface
(method_declaration name: (identifier) @name.definition.method) @definition.method
(namespace_declaration name: (identifier) @name.definition.module) @definition.module
"""
