"""
Snapshot Tests cho prompt output formats.

Dam bao output cua 4 formats (Markdown, XML, JSON, Plain) khong
bi thay doi ngoai y muon sau khi refactoring.

Strategy:
- Tao 2 files (Python + JSON) voi noi dung co dinh
- Goi generate_file_contents_*() cho moi format
- So sanh output voi golden file trong tests/snapshots/
- Neu golden file chua ton tai -> tu dong tao (first run)
- Dung use_relative_paths=True + workspace_root=tmp_path
  de output KHONG chua absolute paths (deterministic)
"""

from pathlib import Path

from core.prompt_generator import (
    generate_file_contents,
    generate_file_contents_xml,
    generate_file_contents_json,
    generate_file_contents_plain,
)

# Thu muc chua golden files
SNAPSHOTS_DIR = Path(__file__).parent / "snapshots"


def _create_test_files(tmp_path: Path) -> set:
    """
    Tao 2 files voi noi dung co dinh de test.
    Return set of absolute paths.
    """
    py_file = tmp_path / "hello.py"
    py_file.write_text('def greet(name):\n    return f"Hello, {name}!"\n')

    json_file = tmp_path / "config.json"
    json_file.write_text('{\n  "version": "1.0",\n  "debug": false\n}\n')

    return {str(py_file), str(json_file)}


def _normalize_output(output: str, tmp_path: Path) -> str:
    """
    Normalize output de loai bo nhung phan thay doi theo environment.
    Replace absolute path prefix bang placeholder.
    """
    # Replace bat ky absolute path prefix nao con sot
    result = output.replace(str(tmp_path), "/WORKSPACE")
    return result


def _load_or_create_snapshot(name: str, actual: str) -> str:
    """
    Load golden file. Neu chua co, tao moi va return actual.
    """
    snapshot_path = SNAPSHOTS_DIR / name
    if snapshot_path.exists():
        return snapshot_path.read_text()
    else:
        # First run -- tao golden file
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(actual)
        return actual


class TestPromptSnapshots:
    """Snapshot tests cho 4 prompt output formats."""

    def test_markdown_format(self, tmp_path):
        """Markdown format output khong thay doi sau refactoring."""
        paths = _create_test_files(tmp_path)
        output = generate_file_contents(
            paths,
            workspace_root=tmp_path,
            use_relative_paths=True,
        )
        normalized = _normalize_output(output, tmp_path)
        expected = _load_or_create_snapshot("markdown_format.txt", normalized)
        assert normalized == expected, (
            "Markdown format output da thay doi!\n"
            "Neu thay doi la co y dinh, xoa tests/snapshots/markdown_format.txt "
            "va chay lai test de tao golden file moi."
        )

    def test_xml_format(self, tmp_path):
        """XML format output khong thay doi sau refactoring."""
        paths = _create_test_files(tmp_path)
        output = generate_file_contents_xml(
            paths,
            workspace_root=tmp_path,
            use_relative_paths=True,
        )
        normalized = _normalize_output(output, tmp_path)
        expected = _load_or_create_snapshot("xml_format.txt", normalized)
        assert normalized == expected, (
            "XML format output da thay doi!\n"
            "Neu thay doi la co y dinh, xoa tests/snapshots/xml_format.txt "
            "va chay lai test de tao golden file moi."
        )

    def test_json_format(self, tmp_path):
        """JSON format output khong thay doi sau refactoring."""
        paths = _create_test_files(tmp_path)
        output = generate_file_contents_json(
            paths,
            workspace_root=tmp_path,
            use_relative_paths=True,
        )
        normalized = _normalize_output(output, tmp_path)
        expected = _load_or_create_snapshot("json_format.txt", normalized)
        assert normalized == expected, (
            "JSON format output da thay doi!\n"
            "Neu thay doi la co y dinh, xoa tests/snapshots/json_format.txt "
            "va chay lai test de tao golden file moi."
        )

    def test_plain_format(self, tmp_path):
        """Plain text format output khong thay doi sau refactoring."""
        paths = _create_test_files(tmp_path)
        output = generate_file_contents_plain(
            paths,
            workspace_root=tmp_path,
            use_relative_paths=True,
        )
        normalized = _normalize_output(output, tmp_path)
        expected = _load_or_create_snapshot("plain_format.txt", normalized)
        assert normalized == expected, (
            "Plain format output da thay doi!\n"
            "Neu thay doi la co y dinh, xoa tests/snapshots/plain_format.txt "
            "va chay lai test de tao golden file moi."
        )
