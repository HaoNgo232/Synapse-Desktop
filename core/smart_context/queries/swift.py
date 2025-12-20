"""Tree-sitter query for Swift - Port từ Repomix querySwift.ts"""

QUERY = """
(comment) @comment

; Class and protocol declarations
(class_declaration name: (type_identifier) @name) @definition.class
(protocol_declaration name: (type_identifier) @name) @definition.interface

; Function declarations
(function_declaration name: (simple_identifier) @name) @definition.function

; Property declarations
(property_declaration (pattern (simple_identifier) @name)) @definition.property
"""
