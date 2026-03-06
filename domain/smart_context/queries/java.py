"""Tree-sitter query for Java - Port từ Repomix queryJava.ts"""

QUERY = """
(line_comment) @comment
(block_comment) @comment
(import_declaration) @definition.import
(package_declaration) @definition.import
(class_declaration name: (identifier) @name.definition.class) @definition.class
(method_declaration name: (identifier) @name.definition.method) @definition.method
(interface_declaration name: (identifier) @name.definition.interface) @definition.interface
"""
