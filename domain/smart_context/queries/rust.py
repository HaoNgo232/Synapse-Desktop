"""Tree-sitter query for Rust - Port từ Repomix queryRust.ts"""

QUERY = """
(line_comment) @comment
(block_comment) @comment
(use_declaration) @definition.import
(struct_item name: (type_identifier) @name.definition.class) @definition.class
(enum_item name: (type_identifier) @name.definition.class) @definition.class
(function_item name: (identifier) @name.definition.function) @definition.function
(trait_item name: (type_identifier) @name.definition.interface) @definition.interface
(mod_item name: (identifier) @name.definition.module) @definition.module
"""
