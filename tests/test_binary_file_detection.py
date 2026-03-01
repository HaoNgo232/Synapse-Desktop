"""
Test binary file detection - đảm bảo binary files KHÔNG có extension
(như Linux/macOS executables) được phát hiện đúng ở TẤT CẢ layers.

Root cause: app bị treo khi checkbox folder chứa binary files lớn (30-42MB)
vì dùng is_binary_by_extension() thay vì is_binary_file().
Files binary không có extension (ELF, Mach-O) bypass extension check
→ bị read_text() đọc toàn bộ → OOM.
"""

import struct
import pytest
from pathlib import Path


class TestIsBinaryFile:
    """Test is_binary_file() detects all binary types"""

    def test_binary_with_extension(self, tmp_path):
        """File có extension binary (.exe) phải được detect"""
        from core.utils.file_utils import is_binary_file

        exe_file = tmp_path / "test.exe"
        exe_file.write_bytes(b"MZ" + b"\x00" * 100)
        assert is_binary_file(exe_file) is True

    def test_binary_without_extension_elf(self, tmp_path):
        """ELF binary (Linux executable) KHÔNG có extension phải được detect"""
        from core.utils.file_utils import is_binary_file

        # ELF magic bytes
        elf_binary = tmp_path / "my-program-x86_64-unknown-linux-gnu"
        elf_binary.write_bytes(b"\x7fELF" + b"\x00" * 100)
        assert is_binary_file(elf_binary) is True

    def test_binary_without_extension_macho(self, tmp_path):
        """Mach-O binary (macOS executable) KHÔNG có extension phải được detect"""
        from core.utils.file_utils import is_binary_file

        # Mach-O magic bytes (64-bit)
        macho_binary = tmp_path / "my-program-aarch64-apple-darwin"
        macho_binary.write_bytes(struct.pack("<I", 0xFEEDFACF) + b"\x00" * 100)
        assert is_binary_file(macho_binary) is True

    def test_binary_without_extension_null_bytes(self, tmp_path):
        """File chứa null bytes phải được detect là binary"""
        from core.utils.file_utils import is_binary_file

        binary_file = tmp_path / "some-binary-no-ext"
        binary_file.write_bytes(b"some data\x00more data\x00" + b"\x00" * 50)
        assert is_binary_file(binary_file) is True

    def test_text_file_not_binary(self, tmp_path):
        """File text thuần KHÔNG phải binary"""
        from core.utils.file_utils import is_binary_file

        text_file = tmp_path / "readme.txt"
        text_file.write_text("Hello world\nThis is text\n")
        assert is_binary_file(text_file) is False

    def test_text_file_without_extension_not_binary(self, tmp_path):
        """File text KHÔNG có extension cũng KHÔNG phải binary"""
        from core.utils.file_utils import is_binary_file

        text_file = tmp_path / "Makefile"
        text_file.write_text("all:\n\techo hello\n")
        assert is_binary_file(text_file) is False

    def test_empty_file_not_binary(self, tmp_path):
        """File rỗng KHÔNG phải binary"""
        from core.utils.file_utils import is_binary_file

        empty_file = tmp_path / "empty"
        empty_file.write_bytes(b"")
        assert is_binary_file(empty_file) is False

    def test_nonexistent_file_not_binary(self, tmp_path):
        """File không tồn tại → False"""
        from core.utils.file_utils import is_binary_file

        missing = tmp_path / "does-not-exist"
        assert is_binary_file(missing) is False


class TestIsBinaryByExtension:
    """Test is_binary_by_extension() chỉ check extension (legacy)"""

    def test_misses_binary_without_extension(self, tmp_path):
        """EXPECTED: is_binary_by_extension MISS binary without extension"""
        from core.utils.file_utils import is_binary_by_extension

        # ELF binary without extension
        elf_file = tmp_path / "cli-proxy-x86_64-linux"
        elf_file.write_bytes(b"\x7fELF" + b"\x00" * 100)

        # This is the BUG - is_binary_by_extension misses it
        assert is_binary_by_extension(elf_file) is False

    def test_detects_binary_with_extension(self, tmp_path):
        """is_binary_by_extension CAN detect .exe"""
        from core.utils.file_utils import is_binary_by_extension

        exe_file = tmp_path / "test.exe"
        exe_file.write_bytes(b"MZ" + b"\x00" * 100)
        assert is_binary_by_extension(exe_file) is True


class TestTokenCountWorkerSkipsBinary:
    """Test TokenCountWorker.run() skip binary files đúng cách"""

    def test_skip_binary_without_extension(self, tmp_path):
        """TokenCountWorker phải skip binary files KHÔNG có extension"""
        from components.file_tree_model import TokenCountWorker

        # Create binary file without extension (giả lập ELF)
        binary_file = tmp_path / "my-binary-x86_64-linux"
        binary_file.write_bytes(b"\x7fELF" + b"\x00" * 1000)

        # Create text file
        text_file = tmp_path / "hello.py"
        text_file.write_text("print('hello')")

        worker = TokenCountWorker([str(binary_file), str(text_file)])

        results = {}

        def capture_batch(batch):
            results.update(batch)

        worker.signals.token_counts_batch.connect(capture_batch)
        worker.run()

        # Binary file should have 0 tokens
        assert results.get(str(binary_file)) == 0
        # Text file should have > 0 tokens
        assert results.get(str(text_file), 0) > 0

    def test_skip_large_file(self, tmp_path):
        """TokenCountWorker phải skip files > 5MB"""
        from components.file_tree_model import TokenCountWorker

        # Create large text file (> 5MB)
        large_file = tmp_path / "huge.txt"
        large_file.write_text("x" * (6 * 1024 * 1024))  # 6MB

        worker = TokenCountWorker([str(large_file)])

        results = {}

        def capture_batch(batch):
            results.update(batch)

        worker.signals.token_counts_batch.connect(capture_batch)
        worker.run()

        # Large file should have 0 tokens (skipped)
        assert results.get(str(large_file)) == 0


class TestGetSelectedPathsSkipsBinary:
    """Test FileTreeModel.get_selected_paths() skip binary files"""

    def test_skip_binary_file_in_selection(self, tmp_path):
        """get_selected_paths phải skip binary files KHÔNG có extension"""
        from components.file_tree_model import FileTreeModel

        # Create files
        binary_file = tmp_path / "my-elf-binary"
        binary_file.write_bytes(b"\x7fELF" + b"\x00" * 100)

        text_file = tmp_path / "code.py"
        text_file.write_text("x = 1")

        model = FileTreeModel()
        model._workspace_path = tmp_path  # Required for get_selected_paths()

        # Simulate: add nodes to model
        from components.file_tree_model import TreeNode

        root_node = TreeNode("root", str(tmp_path), is_dir=True)
        bin_node = TreeNode("my-elf-binary", str(binary_file), is_dir=False)
        txt_node = TreeNode("code.py", str(text_file), is_dir=False)
        root_node.children = [bin_node, txt_node]
        root_node.is_loaded = True

        model._root_node = root_node
        model._invisible_root.children = [root_node]
        model._path_to_node[str(binary_file)] = bin_node
        model._path_to_node[str(text_file)] = txt_node
        model._path_to_node[str(tmp_path)] = root_node

        # Select both files using proper API
        model._selection_mgr.add_many({str(binary_file), str(text_file)})

        selected = model.get_selected_paths()

        # Should NOT include binary file
        assert str(binary_file) not in selected
        # Should include text file
        assert str(text_file) in selected


class TestCollectFilesFromDiskSkipsBinary:
    """Test collect_files_from_disk skip binary files"""

    def test_skip_binary_in_disk_scan(self, tmp_path):
        """collect_files_from_disk phai skip binary KHONG co extension"""
        from services.workspace_index import collect_files_from_disk

        # Create .git dir to anchor root path resolution
        (tmp_path / ".git").mkdir()

        # Create folder with mixed files
        folder = tmp_path / "binaries"
        folder.mkdir()

        binary_file = folder / "server-x86_64-linux"
        binary_file.write_bytes(b"\x7fELF" + b"\x00" * 100)

        text_file = folder / "config.json"
        text_file.write_text('{"key": "value"}')

        result = collect_files_from_disk(folder, workspace_path=tmp_path)

        # Binary file should NOT be in results
        assert str(binary_file) not in result
        # Text file should be in results
        assert str(text_file) in result


class TestPromptGeneratorSkipsBinary:
    """Test prompt generator functions skip binary files without extension"""

    def test_xml_format_skip_binary(self, tmp_path):
        """generate_file_contents_xml phải skip binary KHÔNG có extension"""
        from core.prompt_generator import generate_file_contents_xml

        binary_file = tmp_path / "server-binary"
        binary_file.write_bytes(b"\x7fELF" + b"\x00" * 100)

        text_file = tmp_path / "app.py"
        text_file.write_text("print('hi')")

        result = generate_file_contents_xml({str(binary_file), str(text_file)})

        # Binary file should be marked as skipped
        assert 'skipped="true"' in result or str(binary_file) not in result
        # Text file content should be included
        assert "print" in result

    def test_json_format_skip_binary(self, tmp_path):
        """generate_file_contents_json phải skip binary KHÔNG có extension"""
        import json
        from core.prompt_generator import generate_file_contents_json

        binary_file = tmp_path / "server-binary"
        binary_file.write_bytes(b"\x7fELF" + b"\x00" * 100)

        text_file = tmp_path / "app.py"
        text_file.write_text("print('hi')")

        result = json.loads(
            generate_file_contents_json({str(binary_file), str(text_file)})
        )

        # Binary should be skipped
        if str(binary_file) in result:
            assert (
                "skipped" in result[str(binary_file)].lower()
                or "binary" in result[str(binary_file)].lower()
            )
        # Text file content should be present
        assert "print" in result.get(str(text_file), "")

    def test_plain_format_skip_binary(self, tmp_path):
        """generate_file_contents_plain phải skip binary KHÔNG có extension"""
        from core.prompt_generator import generate_file_contents_plain

        binary_file = tmp_path / "server-binary"
        binary_file.write_bytes(b"\x7fELF" + b"\x00" * 100)

        text_file = tmp_path / "app.py"
        text_file.write_text("print('hi')")

        result = generate_file_contents_plain({str(binary_file), str(text_file)})

        # Binary should be marked as skipped
        assert "Binary file (skipped)" in result or str(binary_file) not in result
        # Text file content should be present
        assert "print" in result


class TestSecurityCheckSkipsBinary:
    """Test security scanning skip binary files without extension"""

    def test_scan_skip_binary(self, tmp_path):
        """scan_secrets_in_files phải skip binary KHÔNG có extension"""
        from core.security_check import scan_secrets_in_files

        binary_file = tmp_path / "server-binary"
        binary_file.write_bytes(b"\x7fELF" + b"\x00" * 100)

        text_file = tmp_path / "config.py"
        text_file.write_text('API_KEY = "safe_value"')

        # Should not crash or try to read binary
        result = scan_secrets_in_files({str(binary_file), str(text_file)})
        # Result should be a list (no crash)
        assert isinstance(result, list)


class TestRealWorldProxypalBinaries:
    """
    Test với actual proxypal-main binaries nếu tồn tại.
    Skip nếu project không có trên máy.
    """

    BINARIES_DIR = Path("/home/hao/Desktop/proxypal-main/src-tauri/binaries")

    @pytest.mark.skipif(
        not Path("/home/hao/Desktop/proxypal-main/src-tauri/binaries").exists(),
        reason="proxypal-main binaries not found",
    )
    def test_all_proxypal_binaries_detected(self):
        """Tất cả binary files trong proxypal phải được is_binary_file detect"""
        from core.utils.file_utils import is_binary_file

        for f in self.BINARIES_DIR.iterdir():
            if f.is_file():
                assert is_binary_file(f), (
                    f"MISSED: {f.name} ({f.stat().st_size // 1024 // 1024}MB)"
                )

    @pytest.mark.skipif(
        not Path("/home/hao/Desktop/proxypal-main/src-tauri/binaries").exists(),
        reason="proxypal-main binaries not found",
    )
    def test_token_worker_skips_proxypal_binaries(self):
        """TokenCountWorker phải skip tất cả proxypal binaries, KHÔNG đọc file"""
        from components.file_tree_model import TokenCountWorker

        binary_paths = [str(f) for f in self.BINARIES_DIR.iterdir() if f.is_file()]
        assert len(binary_paths) > 0, "No binary files found"

        worker = TokenCountWorker(binary_paths)

        results = {}

        def capture_batch(batch):
            results.update(batch)

        worker.signals.token_counts_batch.connect(capture_batch)

        import time

        start = time.time()
        worker.run()
        elapsed = time.time() - start

        # ALL binaries should have 0 tokens
        for bp in binary_paths:
            assert results.get(bp) == 0, f"Binary {bp} was not skipped!"

        # Should complete quickly (< 2s) — not trying to read 200MB+
        assert elapsed < 2.0, f"Took {elapsed:.1f}s — probably reading binary content!"
        print(f"\n✅ Skipped {len(binary_paths)} binaries in {elapsed:.3f}s")
