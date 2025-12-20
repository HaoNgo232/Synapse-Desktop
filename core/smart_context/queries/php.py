"""Tree-sitter query for PHP - Port từ Repomix queryPhp.ts"""

QUERY = """
(comment) @comment

; Namespace and imports
(namespace_definition name: (namespace_name) @name) @definition.module
(namespace_use_clause) @definition.import

; Class declarations
(class_declaration name: (name) @name) @definition.class
(interface_declaration name: (name) @name) @definition.interface
(trait_declaration name: (name) @name) @definition.interface
(enum_declaration name: (name) @name) @definition.enum

; Function and method declarations
(function_definition name: (name) @name) @definition.function
(method_declaration name: (name) @name) @definition.method

; Properties
(property_declaration
  (property_element (variable_name (name) @name))) @definition.field
"""
