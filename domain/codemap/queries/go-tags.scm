; Derived from Aider (based on nvim-treesitter tags) with Synapse Semantic customisations
; 

(comment) @comment
(package_clause) @definition.package
(import_declaration) @definition.import
(import_spec) @definition.import
(var_declaration) @definition.variable
(const_declaration) @definition.constant

(
  (comment)* @doc
  .
  (function_declaration
    name: (identifier) @name.definition.function) @definition.function
  (#strip! @doc "^//\\s*")
  (#set-adjacent! @doc @definition.function)
)

(
  (comment)* @doc
  .
  (method_declaration
    name: (field_identifier) @name.definition.method) @definition.method
  (#strip! @doc "^//\\s*")
  (#set-adjacent! @doc @definition.method)
)

(call_expression
  function: [
    (identifier) @name.reference.call
    (parenthesized_expression (identifier) @name.reference.call)
    (selector_expression field: (field_identifier) @name.reference.call)
    (parenthesized_expression (selector_expression field: (field_identifier) @name.reference.call))
  ]) @reference.call

(type_spec
  name: (type_identifier) @name.definition.type) @definition.type

(type_identifier) @name.reference.type @reference.type

(type_declaration (type_spec name: (type_identifier) @name.definition.interface type: (interface_type)))
(type_declaration (type_spec name: (type_identifier) @name.definition.struct type: (struct_type)))

; Import statements details
(import_declaration
  (import_spec_list
    (import_spec
      path: (interpreted_string_literal) @name.reference.module))) @definition.import

(import_declaration
  (import_spec
    path: (interpreted_string_literal) @name.reference.module)) @definition.import
