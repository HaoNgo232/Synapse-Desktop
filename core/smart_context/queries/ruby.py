"""Tree-sitter query for Ruby - Port từ Repomix queryRuby.ts"""

QUERY = """
(comment) @comment

; Method definitions
(method name: (_) @name.definition.method) @definition.method
(singleton_method name: (_) @name.definition.method) @definition.method
(alias name: (_) @name.definition.method) @definition.method

; Class definitions
(class name: (constant) @name.definition.class) @definition.class
(singleton_class value: (constant) @name.definition.class) @definition.class

; Module definitions
(module name: (constant) @name.definition.module) @definition.module

; Calls
(call method: (identifier) @name.reference.call) @reference.call
"""
