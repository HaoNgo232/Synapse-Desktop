"""
Smart Context Languages - Tree-sitter Language Management

Module quản lý việc load và cache Tree-sitter language grammars.
Hỗ trợ Python, JavaScript, và TypeScript với tree-sitter queries port từ Repomix.

BACKWARD COMPATIBILITY NOTE:
- Existing Python/JavaScript support giữ nguyên APIs
- TypeScript giờ có parser riêng thay vì dùng JavaScript parser
- Queries được thêm mới để improve parsing quality
"""

from typing import Optional, Dict
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tstypescript
import tree_sitter_rust as tsrust
import tree_sitter_go as tsgo
import tree_sitter_java as tsjava
import tree_sitter_c_sharp as tscsharp
import tree_sitter_c as tsc
import tree_sitter_cpp as tscpp
from tree_sitter import Language

# Cache các language đã load để tránh load lại nhiều lần
_language_cache: Dict[str, Language] = {}

# Map từ file extension sang Tree-sitter language
EXTENSION_TO_LANGUAGE: Dict[str, str] = {
    # Python
    "py": "python",
    "pyw": "python",
    # JavaScript
    "js": "javascript",
    "jsx": "javascript",
    "mjs": "javascript",
    "cjs": "javascript",
    "mjsx": "javascript",
    # TypeScript - NOW SEPARATE (not using JavaScript parser configuration anymore)
    "ts": "typescript",
    "tsx": "typescript",
    "mts": "typescript",
    "mtsx": "typescript",
    "cts": "typescript",
    # Rust - NEW in Phase 2
    "rs": "rust",
    # Go - NEW in Phase 2
    "go": "go",
    # Java - NEW in Phase 3
    "java": "java",
    # C# - NEW in Phase 3
    "cs": "c_sharp",
    # C - NEW in Phase 3
    "c": "c",
    "h": "c",
    # C++ - NEW in Phase 3
    "cpp": "cpp",
    "hpp": "cpp",
    "cc": "cpp",
    "hh": "cpp",
    "cxx": "cpp",
    "hxx": "cpp",
}

# Tree-sitter queries ported từ Repomix
# Queries define cách extract structure từ AST
LANGUAGE_QUERIES: Dict[str, str] = {
    # Python query - port từ Repomix queryPython.ts
    "python": """
(comment) @comment

(expression_statement
  (string) @comment) @docstring

; Import statements
(import_statement
  name: (dotted_name) @name.reference.module) @definition.import

(import_from_statement
  module_name: (dotted_name) @name.reference.module) @definition.import

(import_from_statement
  name: (dotted_name) @name.reference.module) @definition.import

(class_definition
  name: (identifier) @name.definition.class) @definition.class

(function_definition
  name: (identifier) @name.definition.function) @definition.function

(call
  function: [
      (identifier) @name.reference.call
      (attribute
        attribute: (identifier) @name.reference.call)
  ]) @reference.call

(assignment
  left: (identifier) @name.definition.type_alias) @definition.type_alias
""",
    # JavaScript query - port từ Repomix queryJavascript.ts
    "javascript": """
(comment) @comment

(
  (comment)* @doc
  .
  (method_definition
    name: (property_identifier) @name.definition.method) @definition.method
  (#not-eq? @name.definition.method "constructor")
  (#strip! @doc "^[\\\\s\\\\*/]+|^[\\\\s\\\\*/]$")
  (#select-adjacent! @doc @definition.method)
)

(
  (comment)* @doc
  .
  [
    (class
      name: (_) @name.definition.class)
    (class_declaration
      name: (_) @name.definition.class)
  ] @definition.class
  (#strip! @doc "^[\\\\s\\\\*/]+|^[\\\\s\\\\*/]$")
  (#select-adjacent! @doc @definition.class)
)

(
  (comment)* @doc
  .
  [
    (function_declaration
      name: (identifier) @name.definition.function)
    (generator_function
      name: (identifier) @name.definition.function)
    (generator_function_declaration
      name: (identifier) @name.definition.function)
  ] @definition.function
  (#strip! @doc "^[\\\\s\\\\*/]+|^[\\\\s\\\\*/]$")
  (#select-adjacent! @doc @definition.function)
)

(
  (comment)* @doc
  .
  (lexical_declaration
    (variable_declarator
      name: (identifier) @name.definition.function
      value: [(arrow_function) (function_declaration)]) @definition.function)
  (#strip! @doc "^[\\\\s\\\\*/]+|^[\\\\s\\\\*/]$")
  (#select-adjacent! @doc @definition.function)
)

(
  (comment)* @doc
  .
  (variable_declaration
    (variable_declarator
      name: (identifier) @name.definition.function
      value: [(arrow_function) (function_declaration)]) @definition.function)
  (#strip! @doc "^[\\\\s\\\\*/]+|^[\\\\s\\\\*/]$")
  (#select-adjacent! @doc @definition.function)
)

(assignment_expression
  left: [
    (identifier) @name.definition.function
    (member_expression
      property: (property_identifier) @name.definition.function)
  ]
  right: [(arrow_function) (function_declaration)]
) @definition.function

(pair
  key: (property_identifier) @name.definition.function
  value: [(arrow_function) (function_declaration)]) @definition.function

(
  (call_expression
    function: (identifier) @name.reference.call) @reference.call
  (#not-match? @name.reference.call "^(require)$")
)

(call_expression
  function: (member_expression
    property: (property_identifier) @name.reference.call)
  arguments: (_) @reference.call)

(new_expression
  constructor: (_) @name.reference.class) @reference.class
""",
    # TypeScript query - port từ Repomix queryTypescript.ts
    "typescript": """
(import_statement
  (import_clause (identifier) @name.reference.module)) @definition.import

(import_statement
  (import_clause
    (named_imports
      (import_specifier
        name: (identifier) @name.reference.module))) @definition.import)

(comment) @comment

(function_signature
  name: (identifier) @name.definition.function) @definition.function

(method_signature
  name: (property_identifier) @name.definition.method) @definition.method

(abstract_method_signature
  name: (property_identifier) @name.definition.method) @definition.method

(abstract_class_declaration
  name: (type_identifier) @name.definition.class) @definition.class

(module
  name: (identifier) @name.definition.module) @definition.module

(interface_declaration
  name: (type_identifier) @name.definition.interface) @definition.interface

(type_annotation
  (type_identifier) @name.reference.type) @reference.type

(new_expression
  constructor: (identifier) @name.reference.class) @reference.class

(function_declaration
  name: (identifier) @name.definition.function) @definition.function

(method_definition
  name: (property_identifier) @name.definition.method) @definition.method

(class_declaration
  name: (type_identifier) @name.definition.class) @definition.class

(interface_declaration
  name: (type_identifier) @name.definition.class) @definition.class

(type_alias_declaration
  name: (type_identifier) @name.definition.type) @definition.type

(enum_declaration
  name: (identifier) @name.definition.enum) @definition.enum

(lexical_declaration
    (variable_declarator
      name: (identifier) @name.definition.function
      value: (arrow_function)
    )
  ) @definition.function

(variable_declaration
    (variable_declarator
      name: (identifier) @name.definition.function
      value: (arrow_function)
    )
) @definition.function

(assignment_expression
    left: [(identifier) @name.definition.function]
    right: (arrow_function)
) @definition.function
""",
    # Rust query - NEW in Phase 2
    "rust": """
(line_comment) @comment
(block_comment) @comment
(use_declaration) @definition.import
(struct_item name: (type_identifier) @name.definition.class) @definition.class
(enum_item name: (type_identifier) @name.definition.class) @definition.class
(function_item name: (identifier) @name.definition.function) @definition.function
""",
    # Go query - NEW in Phase 2
    "go": """
(comment) @comment
(package_clause) @definition.package
(import_declaration) @definition.import
(function_declaration name: (identifier) @name) @definition.function
(method_declaration name: (field_identifier) @name) @definition.method
(type_spec name: (type_identifier) @name) @definition.type
""",
    # Java query - NEW in Phase 3
    "java": """
(line_comment) @comment
(block_comment) @comment
(import_declaration) @definition.import
(package_declaration) @definition.import
(class_declaration name: (identifier) @name.definition.class) @definition.class
(method_declaration name: (identifier) @name.definition.method) @definition.method
(interface_declaration name: (identifier) @name.definition.interface) @definition.interface
""",
    # C# query - NEW in Phase 3
    "c_sharp": """
(comment) @comment
(class_declaration name: (identifier) @name.definition.class) @definition.class
(interface_declaration name: (identifier) @name.definition.interface) @definition.interface
(method_declaration name: (identifier) @name.definition.method) @definition.method
(namespace_declaration name: (identifier) @name.definition.module) @definition.module
""",
    # C query - NEW in Phase 3
    "c": """
(comment) @comment
(struct_specifier name: (type_identifier) @name.definition.class) @definition.class
(function_declarator declarator: (identifier) @name.definition.function) @definition.function
(type_definition declarator: (type_identifier) @name.definition.type) @definition.type
(enum_specifier name: (type_identifier) @name.definition.type) @definition.type
""",
    # C++ query - NEW in Phase 3
    "cpp": """
(comment) @comment
(struct_specifier name: (type_identifier) @name.definition.class) @definition.class
(class_specifier name: (type_identifier) @name.definition.class) @definition.class
(function_declarator declarator: (identifier) @name.definition.function) @definition.function
(type_definition declarator: (type_identifier) @name.definition.type) @definition.type
(enum_specifier name: (type_identifier) @name.definition.type) @definition.type
""",
}


def get_language(extension: str) -> Optional[Language]:
    """
    Lấy Tree-sitter Language dựa trên file extension.

    Args:
        extension: File extension (không có dấu chấm), ví dụ: "py", "js", "ts"

    Returns:
        Language object hoặc None nếu không hỗ trợ

    BACKWARD COMPATIBILITY:
    - Python và JavaScript: Trả về Language như cũ
    - TypeScript: Giờ có Language riêng (JavaScript grammar with TS rules)
    """
    ext_lower = extension.lower()
    lang_name = EXTENSION_TO_LANGUAGE.get(ext_lower)

    if not lang_name:
        return None

    # Kiểm tra cache trước
    if lang_name in _language_cache:
        return _language_cache[lang_name]

    # Load language dựa trên tên
    language: Optional[Language] = None

    if lang_name == "python":
        language = Language(tspython.language())
    elif lang_name == "javascript":
        language = Language(tsjavascript.language())
    elif lang_name == "typescript":
        # Fixed: Use actual TypeScript grammar for proper interface/type support
        language = Language(tstypescript.language_typescript())
    elif lang_name == "rust":
        # NEW in Phase 2: Rust support
        language = Language(tsrust.language())
    elif lang_name == "go":
        # NEW in Phase 2: Go support
        language = Language(tsgo.language())
    elif lang_name == "java":
        # NEW in Phase 3: Java support
        language = Language(tsjava.language())
    elif lang_name == "c_sharp":
        # NEW in Phase 3: C# support
        language = Language(tscsharp.language())
    elif lang_name == "c":
        # NEW in Phase 3: C support
        language = Language(tsc.language())
    elif lang_name == "cpp":
        # NEW in Phase 3: C++ support
        language = Language(tscpp.language())

    # Cache lại kết quả
    if language:
        _language_cache[lang_name] = language

    return language


def get_query(extension: str) -> Optional[str]:
    """
    Lấy tree-sitter query string dựa trên file extension.

    Args:
        extension: File extension (không có dấu chấm)

    Returns:
        Query string hoặc None nếu không hỗ trợ

    NEW in Phase 1: Query-based parsing để improve quality
    """
    ext_lower = extension.lower()
    lang_name = EXTENSION_TO_LANGUAGE.get(ext_lower)

    if not lang_name:
        return None

    return LANGUAGE_QUERIES.get(lang_name)


def is_supported(extension: str) -> bool:
    """
    Kiểm tra xem file extension có được Smart Context hỗ trợ không.

    Args:
        extension: File extension (không có dấu chấm)

    Returns:
        True nếu hỗ trợ, False nếu không

    BACKWARD COMPATIBILITY: API không đổi
    """
    return extension.lower() in EXTENSION_TO_LANGUAGE


def get_supported_extensions() -> list[str]:
    """
    Lấy danh sách các file extensions được hỗ trợ.

    Returns:
        List các extensions (không có dấu chấm)

    BACKWARD COMPATIBILITY: API không đổi
    """
    return list(EXTENSION_TO_LANGUAGE.keys())
