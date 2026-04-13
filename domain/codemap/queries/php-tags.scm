; Derived from Aider (based on nvim-treesitter tags) with Synapse Semantic customisations
; 

(comment) @comment
(namespace_use_clause) @definition.import
(enum_declaration name: (name) @name.definition.enum) @definition.enum

; tree-sitter-php
(namespace_definition
  name: (namespace_name) @name.definition.module) @definition.module

(interface_declaration
  name: (name) @name.definition.interface) @definition.interface

(trait_declaration
  name: (name) @name.definition.interface) @definition.interface

(class_declaration
  name: (name) @name.definition.class) @definition.class

(class_interface_clause [(name) (qualified_name)] @name.reference.implementation) @reference.implementation

(property_declaration
  (property_element (variable_name (name) @name.definition.variable))) @definition.variable

(function_definition
  name: (name) @name.definition.function) @definition.function

(method_declaration
  name: (name) @name.definition.function) @definition.function

(object_creation_expression
  [
    (qualified_name (name) @name.reference.class)
    (variable_name (name) @name.reference.class)
  ]) @reference.class

(function_call_expression
  function: [
    (qualified_name (name) @name.reference.call)
    (variable_name (name)) @name.reference.call
  ]) @reference.call

(scoped_call_expression
  name: (name) @name.reference.call) @reference.call

(member_call_expression
  name: (name) @name.reference.call) @reference.call
