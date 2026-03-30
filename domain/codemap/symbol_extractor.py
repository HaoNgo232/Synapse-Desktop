"""
Symbol Extractor - Extract symbols từ code sử dụng Tree-sitter

Module này parse code và extract tất cả symbols (classes, functions, methods, variables)
với metadata (line numbers, signatures, parent).
"""

from pathlib import Path
from typing import Optional
from tree_sitter import Parser, Node  # type: ignore

from domain.codemap.types import Symbol, SymbolKind
from domain.smart_context.config import get_config_by_extension
from domain.smart_context.loader import get_language


def extract_symbols(file_path: str, content: str) -> list[Symbol]:
    """
    Trích xuất toàn bộ symbols (classes, functions, methods, variables) từ file content.

    Tự động nhận diện nếu file là Điểm Khởi Đầu (Entry Point) của dự án
    để đánh dấu đặc biệt cho AI Reviewer.

    Args:
        file_path: Đường dẫn file (để xác định ngôn ngữ)
        content: Nội dung raw của file

    Returns:
        List các Symbol objects (bao gồm cả dấu hiệu Entry Point nếu có)
    """
    # Lấy file extension (loại bỏ dấu chấm)
    suffix = Path(file_path).suffix
    if not suffix:
        return []

    ext = suffix.lstrip(".")

    # Lấy cấu hình ngôn ngữ tương ứng
    config = get_config_by_extension(ext)
    if not config:
        return []

    language = get_language(ext)
    if not language:
        return []

    try:
        # Parse nội dung sử dụng Tree-sitter
        parser = Parser(language)
        tree = parser.parse(bytes(content, "utf-8"))

        if not tree or not tree.root_node:
            return []

        # Tích lũy kết quả symbols
        symbols: list[Symbol] = []
        lines = content.split("\n")

        # 1. Nhận diện Entry Point (Bootstrapping analysis)
        # Nếu file là điểm khởi đầu, chèn một nhãn Module đặc biệt lên đầu
        if _is_likely_entry_point(file_path, content):
            symbols.append(
                Symbol(
                    name="📍 [ENTRY POINT]",
                    kind=SymbolKind.MODULE,
                    file_path=file_path,
                    line_start=1,
                    line_end=1,
                    signature=f"FILE: {Path(file_path).name} (BOOTSTRAPPER)",
                    parent=None,
                )
            )

        # 2. Duyệt đệ quy cây AST để tìm các thành phần cấu trúc
        _extract_symbols_recursive(
            tree.root_node, lines, file_path, symbols, parent=None
        )

        return symbols

    except Exception:
        # Tránh crash UI nếu có lỗi parse không mong muốn
        return []


def _is_likely_entry_point(file_path: str, content: str) -> bool:
    """
    Kiểm tra xem một file có khả năng là Điểm Khởi Đầu (Entry Point) của dự án hay không.
    Dùng quy luật heuristic dựa trên tên file và nội dung khởi động đặc thù.
    """
    filename = Path(file_path).name.lower()

    # Quy tắc 1: Tên file tiêu chuẩn của các Frameworks phổ biến
    entry_filenames = [
        "main.py",
        "app.py",
        "index.py",
        "manage.py",
        "wsgi.py",
        "server.py",  # Python
        "main.ts",
        "index.ts",
        "app.module.ts",
        "server.ts",
        "start.sh",  # TS/JS
        "main.go",  # Go
    ]
    if filename in entry_filenames:
        return True

    # Quy tắc 2: Chứa các khối lệnh khởi động đặc trưng của Python
    if (
        'if __name__ == "__main__":' in content
        or 'if __name__ == "__main__" ' in content
    ):
        return True

    # Quy tắc 3: Chứa các hàm khởi động phổ biến (NestJS, Express, FastAPI, Uvicorn)
    boot_keywords = ["bootstrap(", "app.listen(", "FastAPI(", "uvicorn.run("]
    if any(k in content for k in boot_keywords):
        return True

    return False


def _extract_symbols_recursive(
    node: Node,
    lines: list[str],
    file_path: str,
    symbols: list[Symbol],
    parent: Optional[str] = None,
) -> None:
    """
    Đệ quy trích xuất các symbols từ cây AST Tree-sitter.

    Hàm này duyệt qua tất cả các nodes và chuyển đổi chúng thành Symbol objects
    nếu node đó đại diện cho một thành phần cấu trúc code (Class, Function, Method, etc.)

    Args:
        node: Node AST hiện tại
        lines: Nội dung file đã split thành dòng
        file_path: Đường dẫn file
        symbols: Danh sách tích lũy kết quả
        parent: Tên của symbol cha (dùng cho methods trong class hoặc functions trong namespace)
    """

    # Thử chuyển đổi node hiện tại thành một Symbol
    symbol = _node_to_symbol(node, lines, file_path, parent)

    if symbol:
        symbols.append(symbol)

        # Nếu symbol hiện tại là một cấu trúc có thể chứa các symbols con (Class, Interface, Namespace, etc.)
        # Chúng ta sẽ set tên nó làm parent cho các levels sâu hơn bên dưới.
        if symbol.kind in [
            SymbolKind.CLASS,
            SymbolKind.INTERFACE,
            SymbolKind.STRUCT,
            SymbolKind.ENUM,
            SymbolKind.TRAIT,
            SymbolKind.MODULE,  # MODULE cho namespaces
        ]:
            parent = symbol.name

    # Tiếp tục duyệt qua các con của node hiện tại
    # Đối với các ngôn ngữ như TS/JS, các thành phần quan trọng nằm trong body của class/interface
    for child in node.children:
        _extract_symbols_recursive(child, lines, file_path, symbols, parent)


def _node_to_symbol(
    node: Node, lines: list[str], file_path: str, parent: Optional[str]
) -> Optional[Symbol]:
    """
    Chuyển đổi một node AST cụ thể thành một đối tượng Symbol nếu nó khớp với các patterns đã định nghĩa.

    Hỗ trợ đa ngôn ngữ thông qua việc kiểm tra các loại node phổ biến của Tree-sitter.
    Phát hiện các cấu trúc đặc thù như Arrow Functions, Decorators, Type Aliases.

    Args:
        node: Node cần kiểm tra
        lines: Nội dung file (các dòng)
        file_path: Đường dẫn file
        parent: Tên symbol cha (nếu có)

    Returns:
        Đối tượng Symbol hoặc None nếu node không phải là một symbol cần quan tâm.
    """
    node_type = node.type

    # 1. Các định nghĩa cấu trúc (Class, Interface, Namespace, Module, Enum)
    # -------------------------------------------------------------------------
    is_class_like = node_type in [
        "class_declaration",  # Java, TS, JS, Go (struct/type), Rust
        "class_definition",  # Python
        "interface_declaration",  # Java, TS
        "enum_declaration",  # Java, TS, Rust
        "struct_item",  # Rust
        "enum_item",  # Rust
        "trait_item",  # Rust
        "impl_item",  # Rust
        "type_declaration",  # Go
        "type_alias_declaration",  # TS: export type User = ...
        "module",  # TS: module Utils { ... }
        "internal_module",  # TS: namespace Utils { ... }
    ]

    if is_class_like:
        name = _extract_name(node, lines)
        if name:
            kind = SymbolKind.CLASS
            if "interface" in node_type:
                kind = SymbolKind.INTERFACE
            elif "struct" in node_type or "struct_item" in node_type:
                kind = SymbolKind.STRUCT
            elif "enum" in node_type or "enum_item" in node_type:
                kind = SymbolKind.ENUM
            elif "trait" in node_type or "trait_item" in node_type:
                kind = SymbolKind.TRAIT
            elif "type_alias" in node_type:
                kind = (
                    SymbolKind.VARIABLE
                )  # Biểu diễn Type Alias dưới dạng Variable/Type tùy framework
            elif "module" in node_type:
                kind = SymbolKind.MODULE

            return Symbol(
                name=name,
                kind=kind,
                file_path=file_path,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=_extract_signature(node, lines),
                parent=None
                if kind != SymbolKind.METHOD
                else parent,  # Class thường không có parent cấp cao
            )

    # 2. Định nghĩa hàm và phương thức (Function, Method, Arrow Function)
    # -------------------------------------------------------------------------
    is_function_like = node_type in [
        "function_definition",  # Python
        "function_declaration",  # TS, JS, Go
        "method_definition",  # TS, JS (Class methods)
        "method_declaration",  # Java, Go
        "function_item",  # Rust
        "constructor_declaration",  # TS, JS, Java
        "arrow_function",  # TS, JS: () => {}
    ]

    if is_function_like:
        name = _extract_name(node, lines)

        # Đặc biệt cho TS Arrow Function: Const x = () => {}.
        # Node arrow_function thường không có name identifier trực tiếp,
        # nó nằm trong variable_declarator cha.
        if not name and node_type == "arrow_function":
            # Thử tìm tên từ node cha (Variable Declarator)
            parent_node = node.parent
            if parent_node and parent_node.type == "variable_declarator":
                name = _extract_name(parent_node, lines)
            elif (
                parent_node and parent_node.type == "public_field_definition"
            ):  # Class prop: logout = () => {}
                name = _extract_name(parent_node, lines)

        # Mặc định cho constructor
        if not name and node_type == "constructor_declaration":
            name = "constructor"

        if name:
            # Xác định kind: Method nếu nằm trong class, ngược lại là Function
            kind = SymbolKind.METHOD if parent else SymbolKind.FUNCTION
            return Symbol(
                name=name,
                kind=kind,
                file_path=file_path,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=_extract_signature(node, lines),
                parent=parent,
            )

    # 3. Import statements
    # -------------------------------------------------------------------------
    if (
        "import" in node_type
        or "use_declaration" in node_type
        or "package_declaration" in node_type
    ):
        name = _extract_import_name(node, lines)
        if name:
            return Symbol(
                name=name,
                kind=SymbolKind.IMPORT,
                file_path=file_path,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                signature=lines[node.start_point[0]].strip()
                if node.start_point[0] < len(lines)
                else None,
                parent=None,
            )

    # 4. Biến và hằng số (Variable, Constant, Propeties)
    # -------------------------------------------------------------------------
    is_variable_like = node_type in [
        "variable_declaration",  # TS, JS
        "lexical_declaration",  # TS, JS (const, let)
        "assignment_statement",  # Python
        "expression_statement",  # Python
        "public_field_definition",  # TS class property
        "field_declaration",  # Java
    ]

    if is_variable_like:
        # Quan trọng: Nếu đây là khai báo function (Arrow function), chúng ta đã bắt ở mục 2.
        # Tránh bắt trùng lặp cùng một line thành cả Function và Variable.
        # Kiểm tra xem child có phải là arrow_function không.
        def _check_arrow(n):
            for c in n.children:
                if c.type == "arrow_function" or _check_arrow(c):
                    return True
            return False

        if _check_arrow(node):
            return None  # Để logic function bên trên xử lý

        name = _extract_name(node, lines)
        if name and node.start_point[0] < len(lines):
            line_idx = node.start_point[0]
            line_content = lines[line_idx].strip()

            # Lọc nhiễu: Chỉ lấy biến cấp cao hoặc class props
            is_valid_scope = (
                not line_content.startswith((" ", "\t")) or parent is not None
            )

            # Tránh lấy biến địa phương trong hàm
            is_inside_fn = False
            curr = node.parent
            while curr:
                if any(t in curr.type for t in ["function", "method", "arrow"]):
                    is_inside_fn = True
                    break
                curr = curr.parent

            if is_valid_scope and not is_inside_fn:
                return Symbol(
                    name=name,
                    kind=SymbolKind.VARIABLE,
                    file_path=file_path,
                    line_start=node.start_point[0] + 1,
                    line_end=node.end_point[0] + 1,
                    signature=line_content[:100],
                    parent=parent,
                )

    return None


def _extract_name(node: Node, lines: list[str]) -> Optional[str]:
    """
    Trích xuất tên (identifier) từ một AST node đại diện cho định nghĩa symbol.

    Hỗ trợ identifier cho biến, class, function, property, v.v.
    Duyệt đệ quy nhẹ các children để tìm identifier đúng nghĩa.
    """
    # Các loại node identifier phổ biến trong Tree-sitter
    id_types = [
        "identifier",
        "property_identifier",
        "field_identifier",
        "name",
        "type_identifier",
        "shorthand_property_identifier",
    ]

    # 1. Thử tìm trong children trực tiếp (Optimization: Fast path)
    for child in node.children:
        if child.type in id_types:
            return child.text.decode("utf-8") if child.text else None

    # 2. Xử lý các cấu trúc bọc (ví dụ variable_declaration chứa variable_declarator)
    if node.type in [
        "variable_declaration",
        "lexical_declaration",
        "variable_declarator",
    ]:
        for child in node.children:
            name = _extract_name(child, lines)
            if name:
                return name

    # 3. Fallback: Nếu chính node đó là identifier
    if node.type in id_types:
        return node.text.decode("utf-8") if node.text else None

    return None


def _extract_signature(node: Node, lines: list[str]) -> Optional[str]:
    """
    Trích xuất signature (phần khai báo) của một symbol với khả năng Semantic (Ngữ nghĩa).

    Hỗ trợ:
    1. Trích xuất Decorators (@Injectable, @property, etc.) nằm phía trước node.
    2. Trích xuất dòng đầu tiên của Docstring/JSDoc để AI hiểu nhanh mục đích code.
    3. Chuẩn hóa format: [Decorators] Signature [Summary]
    """
    start_row = node.start_point[0]
    if start_row >= len(lines):
        return None

    # 1. Trích xuất dòng khai báo chính
    main_line = lines[start_row].strip()

    # 2. Trích xuất Decorators (Duyệt các node anh em đứng trước)
    decorators: list[str] = []
    curr = node.prev_sibling
    while curr and curr.type in ["decorator", "attribute"]:  # attribute cho Rust/Python
        deco_text = curr.text.decode("utf-8").strip() if curr.text else ""
        if deco_text:
            # Rút gọn decorator phức tạp nếu cần (vd: @app.get("/") -> @get)
            decorators.insert(0, deco_text)
        curr = curr.prev_sibling

    # 3. Trích xuất Docstring/JSDoc (Semantic Insight)
    description = ""

    # CASE A: JSDoc (TS/JS) nằm ở sibling ngay phía trước decorator hoặc chính node
    # Tìm comment node ở gần nhất
    comment_node = node.prev_sibling
    # Nếu có decorators, comment nằm trước decorators
    if decorators:
        # Quay lại node đứng trước decorator đầu tiên
        first_deco = node.prev_sibling
        while first_deco and first_deco.type in ["decorator", "attribute"]:
            comment_node = first_deco.prev_sibling
            first_deco = first_deco.prev_sibling

    if comment_node and comment_node.type == "comment":
        description = _parse_doc_text(
            comment_node.text.decode("utf-8") if comment_node.text else ""
        )

    # CASE B: Docstring (Python) nằm bên trong body (Child đầu tiên của block)
    if not description:
        # Duyệt sâu vào body để tìm string node đầu tiên
        body_node = None
        for child in node.children:
            if child.type in [
                "block",
                "statement_block",
                "function_body",
                "class_body",
            ]:
                body_node = child
                break

        if body_node:
            for line_node in body_node.children:
                # Python docstring thường bọc trong expression_statement -> string
                target = line_node
                if line_node.type == "expression_statement":
                    target = line_node.children[0]

                if target.type == "string":
                    description = _parse_doc_text(
                        target.text.decode("utf-8") if target.text else ""
                    )
                    break

    # Clean main signature
    if main_line.endswith(":"):
        main_line = main_line[:-1]
    if main_line.endswith("{"):
        main_line = main_line[:-1].strip()

    # Ghép kết quả thành Signature "Cực kỳ chất lượng"
    final_sig = ""
    if decorators:
        final_sig += " ".join(decorators) + " "

    final_sig += main_line

    if description:
        # Tăng giới hạn độ dài để lấy được toàn bộ hoặc phần lớn nội dung Docstring của user
        # Docstring đa dòng sẽ được trình bày gọn gàng trong khối comment /* ... */
        limit = 500
        short_desc = (
            description[:limit] + "..." if len(description) > limit else description
        )
        final_sig += f"\n    /*\n     {short_desc}\n     */"

    return final_sig


def _parse_doc_text(raw_text: str) -> str:
    """
    Làm sạch toàn bộ nội dung của Docstring/JSDoc, bao gồm cả nội dung đa dòng.

    Thực hiện:
    1. Loại bỏ các ký tự bọc đặc trưng của ngôn ngữ (/**, */, \"\"\", etc.)
    2. Xử lý Indentation (thụt lề) để văn bản trông gọn gàng.
    """
    if not raw_text:
        return ""

    # Loại bỏ các ký tự bọc bên ngoài đối với JSDoc và Python Docstrings
    # (Regex đơn giản: strip các ' " * / ở đầu và cuối)
    content = raw_text.strip().strip("*/'\"").strip()

    if not content:
        return ""

    lines = content.split("\n")

    # Tính toán indentation tối thiểu để thực hiện 'dedent' thủ công
    # (Tránh lấy khoảng trắng thụt lề của file gốc)
    min_indent = 999
    actual_lines = []

    for line in lines:
        stripped = line.lstrip()
        # Chăm sóc JSDoc (thường có dấu * ở đầu mỗi dòng)
        if stripped.startswith("*"):
            stripped = stripped[1:].strip()

        if stripped:  # Chỉ tính dòng có nội dung
            indent = len(line) - len(line.lstrip())
            if indent < min_indent:
                min_indent = indent
            actual_lines.append(stripped)
        else:
            actual_lines.append("")

    # Ghép lại thành một khối văn bản súc tích, giữ nguyên các dòng
    result = "\n     ".join(actual_lines).strip()
    return result


def _extract_import_name(node: Node, lines: list[str]) -> Optional[str]:
    """
    Trích xuất tên module hoặc file từ câu lệnh import/require.
    """
    target_nodes = [
        "dotted_name",
        "module",
        "scoped_identifier",
        "use_list",
        "identifier",
        "package_name",
        "scoped_type_identifier",
        "string",
    ]

    for child in node.children:
        if child.type in target_nodes:
            text = child.text.decode("utf-8") if child.text else ""
            return text.strip("'\"")

    return None
