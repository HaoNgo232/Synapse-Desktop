
from application.services.selection_path_validator import (
    validate_ai_selection,
)


class TestSelectionPathValidator:
    def test_validate_ai_selection_success(self, tmp_path):
        # Setup workspace
        workspace = tmp_path
        (workspace / "main.py").write_text("print('hello')", encoding="utf-8")
        (workspace / "utils").mkdir()
        (workspace / "utils" / "helper.py").write_text(
            "def help(): pass", encoding="utf-8"
        )

        raw_paths = [
            "main.py",
            "utils/helper.py",
            "utils\\helper.py",
        ]  # test normalize separator

        result = validate_ai_selection(str(workspace), raw_paths)

        # Trả về danh sách relative paths chuẩn hóa
        assert result.valid_paths == ["main.py", "utils/helper.py"]
        assert len(result.rejected_paths) == 0
        assert len(result.sensitive_blocked) == 0

    def test_validate_ai_selection_traversal(self, tmp_path):
        workspace = tmp_path
        (workspace / "main.py").write_text("print('hello')", encoding="utf-8")

        # traversal dạng string
        raw_paths = ["main.py", "../outside.txt", "utils/../../outside.py"]

        result = validate_ai_selection(str(workspace), raw_paths)

        assert result.valid_paths == ["main.py"]
        # Có 2 path bị reject do traversal
        rejected_reasons = [reason for _, reason in result.rejected_paths]
        assert any("Path traversal components" in r for r in rejected_reasons)

    def test_validate_ai_selection_absolute(self, tmp_path):
        workspace = tmp_path
        (workspace / "main.py").write_text("print('hello')", encoding="utf-8")

        raw_paths = ["main.py", "/etc/passwd", "C:\\Windows\\System32\\cmd.exe"]

        result = validate_ai_selection(str(workspace), raw_paths)

        assert result.valid_paths == ["main.py"]
        rejected_reasons = [reason for _, reason in result.rejected_paths]
        assert any("Absolute paths are not allowed" in r for r in rejected_reasons)

    def test_validate_ai_selection_escape_boundary(self, tmp_path):
        # workspace và một folder ngoài
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()

        (workspace / "main.py").write_text("print('hello')", encoding="utf-8")
        outside_file = outside_dir / "secret.txt"
        outside_file.write_text("secret content", encoding="utf-8")

        # Cố gắng escape qua relative symlink hoặc dot components (nếu lọt qua bước traversal thô)
        # Tạo symlink trong workspace trỏ ra ngoài
        symlink_path = workspace / "link_outside"
        try:
            symlink_path.symlink_to(outside_file)
        except OSError:
            # Bỏ qua test symlink nếu OS không hỗ trợ
            pass

        raw_paths = ["main.py", "link_outside"]
        result = validate_ai_selection(str(workspace), raw_paths)

        assert result.valid_paths == ["main.py"]

    def test_validate_ai_selection_nonexistent(self, tmp_path):
        workspace = tmp_path
        (workspace / "main.py").write_text("print('hello')", encoding="utf-8")

        raw_paths = ["main.py", "ghost.py"]

        result = validate_ai_selection(str(workspace), raw_paths)

        assert result.valid_paths == ["main.py"]
        rejected_reasons = [reason for _, reason in result.rejected_paths]
        assert any("File does not exist" in r for r in rejected_reasons)

    def test_validate_ai_selection_directory(self, tmp_path):
        workspace = tmp_path
        (workspace / "main.py").write_text("print('hello')", encoding="utf-8")
        (workspace / "utils").mkdir()

        raw_paths = ["main.py", "utils"]

        result = validate_ai_selection(str(workspace), raw_paths)

        assert result.valid_paths == ["main.py"]
        rejected_reasons = [reason for _, reason in result.rejected_paths]
        assert any("Path is not a regular file" in r for r in rejected_reasons)

    def test_validate_ai_selection_sensitive(self, tmp_path):
        workspace = tmp_path
        (workspace / "main.py").write_text("print('hello')", encoding="utf-8")
        (workspace / ".env").write_text("KEY=VALUE", encoding="utf-8")
        (workspace / ".env.local").write_text("KEY=VALUE", encoding="utf-8")
        (workspace / "id_rsa").write_text("KEY", encoding="utf-8")
        (workspace / "cert.pem").write_text("CERT", encoding="utf-8")
        (workspace / "credentials.json").write_text("{}", encoding="utf-8")

        raw_paths = [
            "main.py",
            ".env",
            ".env.local",
            "id_rsa",
            "cert.pem",
            "credentials.json",
        ]

        result = validate_ai_selection(str(workspace), raw_paths)

        assert result.valid_paths == ["main.py"]
        assert set(result.sensitive_blocked) == {
            ".env",
            ".env.local",
            "id_rsa",
            "cert.pem",
            "credentials.json",
        }
        rejected_reasons = [reason for _, reason in result.rejected_paths]
        assert all(
            "Sensitive credential/config file blocked" in r
            for p, r in result.rejected_paths
            if p != "main.py"
        )

    def test_validate_ai_selection_system_folders(self, tmp_path):
        workspace = tmp_path
        (workspace / "main.py").write_text("print('hello')", encoding="utf-8")
        (workspace / ".synapse").mkdir()
        (workspace / ".synapse" / "selection.json").write_text("{}", encoding="utf-8")
        (workspace / ".git").mkdir()
        (workspace / ".git" / "config").write_text("config", encoding="utf-8")

        raw_paths = ["main.py", ".synapse/selection.json", ".git/config"]

        result = validate_ai_selection(str(workspace), raw_paths)

        assert result.valid_paths == ["main.py"]
        rejected_reasons = [reason for _, reason in result.rejected_paths]
        assert any(
            "Internal system folders are excluded" in r for r in rejected_reasons
        )

    def test_validate_ai_selection_max_results(self, tmp_path):
        workspace = tmp_path
        # Tạo 5 files
        paths = []
        for i in range(5):
            filename = f"file{i}.py"
            (workspace / filename).write_text("pass", encoding="utf-8")
            paths.append(filename)

        result = validate_ai_selection(str(workspace), paths, max_results=3)

        # Giới hạn kết quả tối đa là 3
        assert len(result.valid_paths) == 3
        assert result.valid_paths == ["file0.py", "file1.py", "file2.py"]
