"""
QA Tests for Preview Diff Accuracy vs Apply Results.
Verifies that preview diff simulator matches 100% with actual applied results on various complex patch scenarios.
"""

import pytest
from pathlib import Path

from domain.ports.registry import DomainRegistry
from infrastructure.filesystem.file_actions import FileActionsService, apply_file_actions
from domain.prompt.opx_parser import ChangeBlock, FileAction
from application.services.preview_analyzer import generate_preview_diff_lines

@pytest.fixture(autouse=True)
def setup_real_file_actions():
    old_service = DomainRegistry._file_actions_service
    DomainRegistry.register_file_actions_service(FileActionsService())
    yield
    DomainRegistry._file_actions_service = old_service


def test_preview_diff_exact_match(tmp_path: Path) -> None:
    """Kiểm tra xem preview diff và apply thực tế khớp nhau hoàn toàn với exact match."""
    file_name = "exact.py"
    target = tmp_path / file_name
    original_content = "def hello():\n    print('Hello World')\n"
    target.write_text(original_content, encoding="utf-8")

    action = FileAction(
        path=file_name,
        action="modify",
        changes=[
            ChangeBlock(
                description="Update hello function",
                search="    print('Hello World')",
                content="    print('Hello Universe')",
            )
        ],
    )

    # 1. Sinh preview diff lines
    preview_diff = generate_preview_diff_lines(action, workspace_root=tmp_path)

    # 2. Thực thi apply thực tế
    results = apply_file_actions([action], workspace_roots=[tmp_path])
    assert results[0].success
    applied_content = target.read_text(encoding="utf-8")

    # 3. So sánh
    from domain.diff.generator import generate_diff_lines

    # Chuẩn hóa line endings của original_content giống như Python read_text()
    original_normalized = original_content.replace("\r\n", "\n")
    expected_diff = generate_diff_lines(original_normalized, applied_content, file_name)

    # So sánh từng dòng diff
    assert len(preview_diff) == len(expected_diff)
    for p_line, e_line in zip(preview_diff, expected_diff):
        assert p_line.type == e_line.type
        assert p_line.content == e_line.content


def test_preview_diff_eol_normalization(tmp_path: Path) -> None:
    """Kiểm tra độ chính xác preview khi file dùng CRLF (\\r\\n) và search string dùng LF (\\n)."""
    file_name = "eol.py"
    target = tmp_path / file_name
    # File dùng CRLF
    original_content = "line1\r\nline2\r\nline3\r\n"
    target.write_bytes(original_content.encode("utf-8"))

    action = FileAction(
        path=file_name,
        action="modify",
        changes=[
            ChangeBlock(
                description="Replace middle line",
                # Search dùng LF
                search="line2\nline3",
                content="replaced2\nreplaced3",
            )
        ],
    )

    # 1. Sinh preview diff lines
    preview_diff = generate_preview_diff_lines(action, workspace_root=tmp_path)

    # 2. Thực thi apply thực tế
    results = apply_file_actions([action], workspace_roots=[tmp_path])
    assert results[0].success
    applied_content = target.read_text(encoding="utf-8")

    # 3. So sánh preview diff với diff thực tế
    from domain.diff.generator import generate_diff_lines

    # Chuẩn hóa line endings của original_content giống như Python read_text()
    original_normalized = original_content.replace("\r\n", "\n")
    expected_diff = generate_diff_lines(original_normalized, applied_content, file_name)

    assert len(preview_diff) == len(expected_diff)
    for p_line, e_line in zip(preview_diff, expected_diff):
        assert p_line.type == e_line.type
        assert p_line.content == e_line.content


def test_preview_diff_normalized_whitespace(tmp_path: Path) -> None:
    """Kiểm tra độ chính xác preview khi file có extra trailing spaces nhưng search block thì không."""
    file_name = "whitespace.py"
    target = tmp_path / file_name
    # File gốc có extra trailing spaces
    original_content = "def sample():    \n    x = 1 \n    return x\n"
    target.write_text(original_content, encoding="utf-8")

    action = FileAction(
        path=file_name,
        action="modify",
        changes=[
            ChangeBlock(
                description="Update variable value",
                # Search block sạch sẽ
                search="    x = 1\n    return x",
                content="    x = 2\n    return x",
            )
        ],
    )

    # 1. Sinh preview diff
    preview_diff = generate_preview_diff_lines(action, workspace_root=tmp_path)

    # 2. Thực thi apply thực tế
    results = apply_file_actions([action], workspace_roots=[tmp_path])
    assert results[0].success
    applied_content = target.read_text(encoding="utf-8")

    # 3. So sánh
    from domain.diff.generator import generate_diff_lines

    original_normalized = original_content.replace("\r\n", "\n")
    expected_diff = generate_diff_lines(original_normalized, applied_content, file_name)

    assert len(preview_diff) == len(expected_diff)
    for p_line, e_line in zip(preview_diff, expected_diff):
        assert p_line.type == e_line.type
        assert p_line.content == e_line.content


def test_preview_diff_fuzzy_match(tmp_path: Path) -> None:
    """Kiểm tra độ chính xác preview khi cần fuzzy matching (ví dụ lệch text nhẹ dưới 10%)."""
    file_name = "fuzzy.py"
    target = tmp_path / file_name
    original_content = "def calculate_total(price, tax):\n    # Calculate tax amount\n    amount = price * tax\n    return amount\n"
    target.write_text(original_content, encoding="utf-8")

    action = FileAction(
        path=file_name,
        action="modify",
        changes=[
            ChangeBlock(
                description="Fix typo in comment and calculation",
                # Search block có sai lệch nhẹ (thiếu chữ 'amount' trong comment)
                search="def calculate_total(price, tax):\n    # Calculate tax\n    amount = price * tax\n    return amount",
                content="def calculate_total(price, tax):\n    # Calculate tax amount\n    amount = price * (tax + 0.1)\n    return amount",
            )
        ],
    )

    # 1. Sinh preview diff
    preview_diff = generate_preview_diff_lines(action, workspace_root=tmp_path)

    # 2. Thực thi apply thực tế
    results = apply_file_actions([action], workspace_roots=[tmp_path])
    assert results[0].success
    applied_content = target.read_text(encoding="utf-8")

    # 3. So sánh
    from domain.diff.generator import generate_diff_lines

    original_normalized = original_content.replace("\r\n", "\n")
    expected_diff = generate_diff_lines(original_normalized, applied_content, file_name)

    assert len(preview_diff) == len(expected_diff)
    for p_line, e_line in zip(preview_diff, expected_diff):
        assert p_line.type == e_line.type
        assert p_line.content == e_line.content
