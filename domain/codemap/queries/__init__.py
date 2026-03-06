"""
Tree-sitter Queries cho Relationship Extraction

Queries để extract function calls, class inheritance, và references.
"""

# ========================================
# Python Queries
# ========================================

QUERY_PYTHON_CALLS = """
; Function calls: foo()
(call
  function: (identifier) @call.function)

; Method calls: obj.method()
(call
  function: (attribute
    object: (identifier) @call.object
    attribute: (identifier) @call.method))

; Chained calls: obj.method1().method2()
(call
  function: (attribute) @call.chained)
"""

QUERY_PYTHON_INHERITANCE = """
; Class inheritance: class Foo(Bar, Baz)
(class_definition
  name: (identifier) @class.name
  superclasses: (argument_list
    (identifier) @class.base))

; Class inheritance with attributes: class Foo(module.Bar)
(class_definition
  name: (identifier) @class.name
  superclasses: (argument_list
    (attribute) @class.base_attr))
"""

# ========================================
# JavaScript/TypeScript Queries
# ========================================

QUERY_JS_CALLS = """
; Function calls: foo()
(call_expression
  function: (identifier) @call.function)

; Method calls: obj.method()
(call_expression
  function: (member_expression
    object: (identifier) @call.object
    property: (property_identifier) @call.method))
"""

QUERY_JS_INHERITANCE = """
; Class extends: class Foo extends Bar
(class_declaration
  name: (identifier) @class.name
  heritage: (class_heritage
    (identifier) @class.base))

; Class extends member expression: class Foo extends React.Component
(class_declaration
  name: (identifier) @class.name
  heritage: (class_heritage
    (member_expression) @class.base_attr))
"""

QUERY_JS_IMPORTS = """
; ES module import: import x from 'module'
(import_statement
  source: (string) @import.source)

; Re-export from module: export {x} from 'module' / export * from 'module'
(export_statement
  source: (string) @import.source)

; CommonJS require('module')
(call_expression
  function: (identifier) @func (#eq? @func "require")
  arguments: (arguments (string) @import.source))
"""

# ========================================
# Go Queries
# ========================================

QUERY_GO_CALLS = """
; Function calls: foo()
(call_expression
  function: (identifier) @call.function)

; Method calls: obj.Method()
(call_expression
  function: (selector_expression
    operand: (identifier) @call.object
    field: (field_identifier) @call.method))
"""

# ========================================
# Rust Queries
# ========================================

QUERY_RUST_CALLS = """
; Function calls: foo()
(call_expression
  function: (identifier) @call.function)

; Method calls: obj.method()
(call_expression
  function: (field_expression
    value: (identifier) @call.object
    field: (field_identifier) @call.method))
"""

QUERY_RUST_INHERITANCE = """
; Trait implementation: impl Trait for Struct
(impl_item
  trait: (type_identifier) @impl.trait
  type: (type_identifier) @impl.type)
"""
