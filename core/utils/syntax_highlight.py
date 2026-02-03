"""
Syntax highlighting utilities using Pygments for file preview.

Dracula theme colors cho dark mode OLED.
"""

import flet as ft
from typing import List, Tuple
from pygments import lex
from pygments.lexers import get_lexer_by_name, get_lexer_for_filename, TextLexer
from pygments.token import Token


# Dracula color scheme - optimized cho dark OLED theme
DRACULA_COLORS = {
    Token.Text: "#f8f8f2",
    Token.Whitespace: "#f8f8f2",
    Token.Error: "#ff5555",
    Token.Other: "#f8f8f2",
    
    # Comments
    Token.Comment: "#6272a4",
    Token.Comment.Hashbang: "#6272a4",
    Token.Comment.Multiline: "#6272a4",
    Token.Comment.Preproc: "#ff79c6",
    Token.Comment.Single: "#6272a4",
    Token.Comment.Special: "#6272a4",
    
    # Keywords
    Token.Keyword: "#ff79c6",
    Token.Keyword.Constant: "#ff79c6",
    Token.Keyword.Declaration: "#ff79c6",
    Token.Keyword.Namespace: "#ff79c6",
    Token.Keyword.Pseudo: "#ff79c6",
    Token.Keyword.Reserved: "#ff79c6",
    Token.Keyword.Type: "#8be9fd",
    
    # Operators
    Token.Operator: "#ff79c6",
    Token.Operator.Word: "#ff79c6",
    
    # Punctuation
    Token.Punctuation: "#f8f8f2",
    
    # Names
    Token.Name: "#f8f8f2",
    Token.Name.Attribute: "#50fa7b",
    Token.Name.Builtin: "#8be9fd",
    Token.Name.Builtin.Pseudo: "#8be9fd",
    Token.Name.Class: "#50fa7b",
    Token.Name.Constant: "#bd93f9",
    Token.Name.Decorator: "#50fa7b",
    Token.Name.Entity: "#f8f8f2",
    Token.Name.Exception: "#f8f8f2",
    Token.Name.Function: "#50fa7b",
    Token.Name.Function.Magic: "#50fa7b",
    Token.Name.Label: "#8be9fd",
    Token.Name.Namespace: "#f8f8f2",
    Token.Name.Other: "#f8f8f2",
    Token.Name.Tag: "#ff79c6",
    Token.Name.Variable: "#f8f8f2",
    Token.Name.Variable.Class: "#8be9fd",
    Token.Name.Variable.Global: "#f8f8f2",
    Token.Name.Variable.Instance: "#f8f8f2",
    Token.Name.Variable.Magic: "#8be9fd",
    
    # Literals
    Token.Literal: "#f8f8f2",
    Token.Literal.Date: "#f8f8f2",
    
    # Strings
    Token.String: "#f1fa8c",
    Token.String.Affix: "#f1fa8c",
    Token.String.Backtick: "#f1fa8c",
    Token.String.Char: "#f1fa8c",
    Token.String.Delimiter: "#f1fa8c",
    Token.String.Doc: "#f1fa8c",
    Token.String.Double: "#f1fa8c",
    Token.String.Escape: "#ff79c6",
    Token.String.Heredoc: "#f1fa8c",
    Token.String.Interpol: "#f1fa8c",
    Token.String.Other: "#f1fa8c",
    Token.String.Regex: "#f1fa8c",
    Token.String.Single: "#f1fa8c",
    Token.String.Symbol: "#f1fa8c",
    
    # Numbers
    Token.Number: "#bd93f9",
    Token.Number.Bin: "#bd93f9",
    Token.Number.Float: "#bd93f9",
    Token.Number.Hex: "#bd93f9",
    Token.Number.Integer: "#bd93f9",
    Token.Number.Integer.Long: "#bd93f9",
    Token.Number.Oct: "#bd93f9",
    
    # Generic (diffs, etc)
    Token.Generic: "#f8f8f2",
    Token.Generic.Deleted: "#ff5555",
    Token.Generic.Emph: "#f8f8f2",
    Token.Generic.Error: "#ff5555",
    Token.Generic.Heading: "#50fa7b",
    Token.Generic.Inserted: "#50fa7b",
    Token.Generic.Output: "#f8f8f2",
    Token.Generic.Prompt: "#f8f8f2",
    Token.Generic.Strong: "#f8f8f2",
    Token.Generic.Subheading: "#50fa7b",
    Token.Generic.Traceback: "#ff5555",
}


def get_token_color(token_type) -> str:
    """
    Lấy màu cho token type từ Dracula theme.
    
    Args:
        token_type: Pygments token type
        
    Returns:
        Hex color string
    """
    # Tìm màu chính xác hoặc parent token type
    while token_type:
        if token_type in DRACULA_COLORS:
            return DRACULA_COLORS[token_type]
        token_type = token_type.parent
    
    # Fallback
    return "#f8f8f2"


def create_highlighted_text(
    content: str, 
    language: str,
    file_path: str = ""
) -> ft.Text:
    """
    Tạo ft.Text với syntax highlighting sử dụng Pygments và Dracula theme.
    
    Args:
        content: Nội dung code cần highlight
        language: Language hint (python, javascript, etc.)
        file_path: Đường dẫn file (dùng để detect lexer nếu language không rõ)
        
    Returns:
        ft.Text control với TextSpans được highlight
    """
    try:
        # Lấy lexer phù hợp
        if file_path:
            try:
                lexer = get_lexer_for_filename(file_path)
            except Exception:
                lexer = get_lexer_by_name(language.lower()) if language else TextLexer()
        else:
            lexer = get_lexer_by_name(language.lower()) if language else TextLexer()
    except Exception:
        # Fallback to plain text
        lexer = TextLexer()
    
    # Tokenize content
    tokens = list(lex(content, lexer))
    
    # Tạo TextSpans với màu sắc
    spans: List[ft.TextSpan] = []
    
    for token_type, token_value in tokens:
        color = get_token_color(token_type)
        spans.append(
            ft.TextSpan(
                text=token_value,
                style=ft.TextStyle(
                    color=color,
                    font_family="monospace",
                ),
            )
        )
    
    # Tạo Text control với spans
    return ft.Text(
        spans=spans,
        size=13,  # Tăng từ 12 lên 13 để dễ đọc
        selectable=True,
    )
