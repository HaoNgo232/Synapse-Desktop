(comment) @comment

(class_declaration
  name: (type_identifier) @name.definition.class) @definition.class

(protocol_declaration
  name: (type_identifier) @name.definition.interface) @definition.interface

(class_body
  [
    (function_declaration
      name: (simple_identifier) @name.definition.method
    ) @definition.method
    (subscript_declaration) @name.definition.method
    (init_declaration "init" @name.definition.method) @definition.method
    (deinit_declaration "deinit" @name.definition.method) @definition.method
  ]
)

(protocol_body
  [
    (protocol_function_declaration
      name: (simple_identifier) @name.definition.method
    ) @definition.method
    (subscript_declaration) @name.definition.method
    (init_declaration "init" @name.definition.method) @definition.method
  ]
)

(class_body
  [
    (property_declaration
      (pattern (simple_identifier) @name.definition.variable)
    ) @definition.variable
  ]
)

(property_declaration
    (pattern (simple_identifier) @name.definition.variable)
) @definition.variable

(function_declaration
    name: (simple_identifier) @name.definition.function) @definition.function
