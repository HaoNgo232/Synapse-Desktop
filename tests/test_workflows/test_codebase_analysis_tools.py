"""
Tests cho 4 MCP tools moi: get_callers, get_related_tests, batch_codemap, explain_architecture.

Cac tests goi truc tiep ham tool (khong qua MCP protocol)
de kiem tra logic chinh xac tren workspace gia lap.
"""

import pytest

# Import truc tiep cac tool functions tu server module
# Cac ham nay la module-level functions, co the goi truc tiep
from mcp_server.server import (
    get_callers,
    get_related_tests,
    batch_codemap,
    explain_architecture,
)


# ===================================================================
# Fixtures - Tao workspace gia lap cho moi test
# ===================================================================


@pytest.fixture
def python_workspace(tmp_path):
    """
    Workspace Python day du voi source files, test files, va dependencies.
    Cau truc:
        project/
        ├── pyproject.toml
        ├── main.py           (entry point)
        ├── auth/
        │   ├── __init__.py
        │   ├── login.py      (source: login, logout, validate_token)
        │   └── token.py      (source: generate_token, goi validate_token)
        ├── services/
        │   ├── __init__.py
        │   └── user.py       (source: create_user, goi login)
        └── tests/
            ├── __init__.py
            ├── test_login.py  (test: test_login_success, test_login_failure)
            └── test_user.py   (test: test_create_user)
    """
    ws = tmp_path / "project"
    ws.mkdir()

    # Config
    (ws / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n'
    )

    # Entry point
    (ws / "main.py").write_text(
        "from auth.login import login\n"
        "from services.user import create_user\n"
        "\n"
        "def main():\n"
        "    user = login('admin', 'pass')\n"
        "    create_user('new_user')\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )

    # auth/
    auth_dir = ws / "auth"
    auth_dir.mkdir()
    (auth_dir / "__init__.py").write_text("")

    (auth_dir / "login.py").write_text(
        "def login(username, password):\n"
        '    """Dang nhap user."""\n'
        "    validate_token('dummy')\n"
        "    return {'user': username}\n"
        "\n"
        "def logout(session):\n"
        '    """Dang xuat user."""\n'
        "    pass\n"
        "\n"
        "def validate_token(token):\n"
        '    """Kiem tra token hop le."""\n'
        "    return token == 'valid'\n"
    )

    (auth_dir / "token.py").write_text(
        "from auth.login import validate_token\n"
        "\n"
        "def generate_token(user_id):\n"
        '    """Tao token moi."""\n'
        "    token = f'token_{user_id}'\n"
        "    validate_token(token)\n"
        "    return token\n"
        "\n"
        "def refresh_token(old_token):\n"
        '    """Lam moi token."""\n'
        "    if validate_token(old_token):\n"
        "        return generate_token('refreshed')\n"
        "    return None\n"
    )

    # services/
    svc_dir = ws / "services"
    svc_dir.mkdir()
    (svc_dir / "__init__.py").write_text("")

    (svc_dir / "user.py").write_text(
        "from auth.login import login\n"
        "\n"
        "class UserService:\n"
        "    def create_user(self, name):\n"
        '        """Tao user moi."""\n'
        "        result = login(name, 'default_pass')\n"
        "        return result\n"
        "\n"
        "def create_user(name):\n"
        '    """Ham tien ich tao user."""\n'
        "    svc = UserService()\n"
        "    return svc.create_user(name)\n"
    )

    # tests/
    tests_dir = ws / "tests"
    tests_dir.mkdir()
    (tests_dir / "__init__.py").write_text("")

    (tests_dir / "test_login.py").write_text(
        "from auth.login import login\n"
        "\n"
        "def test_login_success():\n"
        "    result = login('admin', 'pass')\n"
        "    assert result is not None\n"
        "\n"
        "def test_login_failure():\n"
        "    result = login('', '')\n"
        "    assert result is not None\n"
    )

    (tests_dir / "test_user.py").write_text(
        "from services.user import create_user\n"
        "\n"
        "def test_create_user():\n"
        "    result = create_user('test')\n"
        "    assert result is not None\n"
    )

    return ws


@pytest.fixture
def empty_workspace(tmp_path):
    """Workspace rong, chi co 1 file khong phai code."""
    ws = tmp_path / "empty"
    ws.mkdir()
    (ws / "README.md").write_text("# Empty project\n")
    return ws


@pytest.fixture
def js_workspace(tmp_path):
    """
    Workspace JavaScript voi test files theo naming convention JS.
    Cau truc:
        jsproject/
        ├── package.json
        ├── src/
        │   ├── utils.ts
        │   └── api.ts
        └── src/
            ├── utils.test.ts
            └── api.spec.ts
    """
    ws = tmp_path / "jsproject"
    ws.mkdir()

    (ws / "package.json").write_text(
        '{"name": "test-project", "devDependencies": {"jest": "^29.0"}}\n'
    )

    src = ws / "src"
    src.mkdir()
    (src / "utils.ts").write_text(
        "export function formatDate(d: Date): string {\n"
        "  return d.toISOString();\n"
        "}\n"
        "\n"
        "export function parseCSV(data: string): string[][] {\n"
        "  return data.split('\\n').map(row => row.split(','));\n"
        "}\n"
    )
    (src / "api.ts").write_text(
        "import { formatDate } from './utils';\n"
        "\n"
        "export async function fetchData(url: string): Promise<any> {\n"
        "  const d = formatDate(new Date());\n"
        "  return { url, timestamp: d };\n"
        "}\n"
    )

    # Test files canh source
    (src / "utils.test.ts").write_text(
        "import { formatDate } from './utils';\n"
        "\n"
        "test('formatDate returns ISO string', () => {\n"
        "  expect(formatDate(new Date())).toBeDefined();\n"
        "});\n"
    )
    (src / "api.spec.ts").write_text(
        "import { fetchData } from './api';\n"
        "\n"
        "describe('fetchData', () => {\n"
        "  it('returns data', async () => {\n"
        "    const result = await fetchData('http://test.com');\n"
        "    expect(result).toBeDefined();\n"
        "  });\n"
        "});\n"
    )

    return ws


# ===================================================================
# Tool 16: get_callers - Tim functions goi mot symbol
# ===================================================================


class TestGetCallers:
    """Tests cho tool get_callers."""

    def test_find_callers_of_function(self, python_workspace):
        """Tim duoc tat ca noi goi validate_token."""
        result = get_callers(
            workspace_path=str(python_workspace),
            symbol_name="validate_token",
        )
        assert "callers of `validate_token`" in result
        # login.py goi validate_token trong ham login
        assert "login" in result.lower()
        # token.py goi validate_token trong generate_token va refresh_token
        assert "token.py" in result

    def test_find_callers_of_login(self, python_workspace):
        """Tim callers cua login function."""
        result = get_callers(
            workspace_path=str(python_workspace),
            symbol_name="login",
        )
        assert "callers of `login`" in result
        # main.py va test_login.py goi login
        assert "main.py" in result

    def test_no_callers_found(self, python_workspace):
        """Symbol khong ton tai -> thong bao khong tim thay."""
        result = get_callers(
            workspace_path=str(python_workspace),
            symbol_name="nonexistent_function_xyz",
        )
        assert "No callers found" in result

    def test_filter_by_extension(self, python_workspace):
        """Chi tim trong files .py, loai bo cac extension khac."""
        result = get_callers(
            workspace_path=str(python_workspace),
            symbol_name="validate_token",
            file_extensions=[".py"],
        )
        assert "Error" not in result

    def test_max_results_limit(self, python_workspace):
        """Gioi han so ket qua tra ve."""
        result = get_callers(
            workspace_path=str(python_workspace),
            symbol_name="validate_token",
            max_results=1,
        )
        # Chi tra ve toi da 1 caller
        lines_with_L = [
            line_str
            for line_str in result.splitlines()
            if line_str.strip().startswith("L")
        ]
        assert len(lines_with_L) <= 1

    def test_invalid_workspace(self):
        """Workspace khong hop le -> tra ve Error."""
        result = get_callers(
            workspace_path="/nonexistent/path",
            symbol_name="foo",
        )
        assert "Error" in result

    def test_caller_includes_enclosing_function(self, python_workspace):
        """Ket qua cho biet ten function chua loi goi (enclosing function)."""
        result = get_callers(
            workspace_path=str(python_workspace),
            symbol_name="validate_token",
        )
        # generate_token goi validate_token
        assert "generate_token" in result or "refresh_token" in result

    def test_skips_definition_line(self, python_workspace):
        """Khong tinh dong dinh nghia (def validate_token) la caller."""
        result = get_callers(
            workspace_path=str(python_workspace),
            symbol_name="validate_token",
        )
        # Kiem tra khong co dong "def validate_token" trong output
        for line in result.splitlines():
            if line.strip().startswith("L"):
                assert "def validate_token" not in line


# ===================================================================
# Tool 17: get_related_tests - Tim test files cho source files
# ===================================================================


class TestGetRelatedTests:
    """Tests cho tool get_related_tests."""

    def test_find_python_tests(self, python_workspace):
        """Tim test files cho Python source file."""
        result = get_related_tests(
            workspace_path=str(python_workspace),
            file_paths=["auth/login.py"],
        )
        assert "test_login" in result
        assert "Found tests for" in result

    def test_find_tests_for_multiple_files(self, python_workspace):
        """Tim tests cho nhieu source files cung luc."""
        result = get_related_tests(
            workspace_path=str(python_workspace),
            file_paths=["auth/login.py", "services/user.py"],
        )
        assert "test_login" in result
        assert "test_user" in result

    def test_no_tests_found(self, python_workspace):
        """Source file khong co test tuong ung."""
        result = get_related_tests(
            workspace_path=str(python_workspace),
            file_paths=["auth/token.py"],
        )
        # token.py khong co test_token.py nen co the khong tim thay
        # (hoac tim thay qua fuzzy match nếu co)
        # Chi can dam bao khong crash
        assert "Error" not in result

    def test_find_js_tests(self, js_workspace):
        """Tim test files cho TypeScript source file."""
        result = get_related_tests(
            workspace_path=str(js_workspace),
            file_paths=["src/utils.ts"],
        )
        assert "utils.test.ts" in result

    def test_find_spec_files(self, js_workspace):
        """Tim .spec.ts files."""
        result = get_related_tests(
            workspace_path=str(js_workspace),
            file_paths=["src/api.ts"],
        )
        assert "api.spec.ts" in result

    def test_invalid_workspace(self):
        """Workspace khong hop le -> tra ve Error."""
        result = get_related_tests(
            workspace_path="/nonexistent/path",
            file_paths=["foo.py"],
        )
        assert "Error" in result

    def test_empty_file_paths(self, python_workspace):
        """Danh sach file_paths rong -> khong tim thay gi."""
        result = get_related_tests(
            workspace_path=str(python_workspace),
            file_paths=[],
        )
        assert "No related test files found" in result


# ===================================================================
# Tool 18: batch_codemap - Codemap cho toan bo directory
# ===================================================================


class TestBatchCodemap:
    """Tests cho tool batch_codemap."""

    def test_codemap_entire_workspace(self, python_workspace):
        """Tao codemap cho toan bo workspace."""
        result = batch_codemap(
            workspace_path=str(python_workspace),
            directory=".",
        )
        assert "Error" not in result
        # Phai chua thong tin ve cac files
        assert "Codemap" in result

    def test_codemap_subdirectory(self, python_workspace):
        """Tao codemap cho subdirectory cu the."""
        result = batch_codemap(
            workspace_path=str(python_workspace),
            directory="auth",
        )
        assert "Error" not in result
        assert "Codemap" in result
        # Phai chua thong tin ve auth module
        assert "login" in result.lower() or "auth" in result.lower()

    def test_codemap_with_extension_filter(self, python_workspace):
        """Filter theo extension chi lay .py files."""
        result = batch_codemap(
            workspace_path=str(python_workspace),
            directory=".",
            extensions=[".py"],
        )
        assert "Error" not in result
        assert "Codemap" in result

    def test_codemap_nonexistent_directory(self, python_workspace):
        """Directory khong ton tai -> tra ve Error."""
        result = batch_codemap(
            workspace_path=str(python_workspace),
            directory="nonexistent",
        )
        assert "Error" in result
        assert "Directory not found" in result

    def test_codemap_path_traversal(self, python_workspace):
        """Path traversal -> bi chan."""
        result = batch_codemap(
            workspace_path=str(python_workspace),
            directory="../../../etc",
        )
        assert "Error" in result

    def test_codemap_invalid_workspace(self):
        """Workspace khong hop le -> tra ve Error."""
        result = batch_codemap(
            workspace_path="/nonexistent/path",
        )
        assert "Error" in result

    def test_codemap_max_files_limit(self, python_workspace):
        """Gioi han so files xu ly."""
        result = batch_codemap(
            workspace_path=str(python_workspace),
            directory=".",
            max_files=2,
        )
        # Khong crash, van tra ket qua
        assert "Error" not in result

    def test_codemap_empty_directory(self, tmp_path):
        """Directory khong co code files -> thong bao."""
        ws = tmp_path / "no_code"
        ws.mkdir()
        sub = ws / "data"
        sub.mkdir()
        (sub / "notes.txt").write_text("just notes")

        result = batch_codemap(
            workspace_path=str(ws),
            directory="data",
        )
        assert "No supported code files" in result


# ===================================================================
# Tool 19: explain_architecture - Architecture summary
# ===================================================================


class TestExplainArchitecture:
    """Tests cho tool explain_architecture."""

    def test_basic_architecture(self, python_workspace):
        """Tao architecture summary cho Python workspace."""
        result = explain_architecture(
            workspace_path=str(python_workspace),
        )
        assert "Architecture:" in result
        assert "Modules" in result
        # Phai detect entry point main.py
        assert "main.py" in result

    def test_detects_modules(self, python_workspace):
        """Nhan dien cac top-level modules."""
        result = explain_architecture(
            workspace_path=str(python_workspace),
        )
        # auth/, services/, tests/ la cac modules
        assert "auth" in result.lower()
        assert "services" in result.lower()
        assert "tests" in result.lower()

    def test_detects_config_files(self, python_workspace):
        """Nhan dien config files (pyproject.toml)."""
        result = explain_architecture(
            workspace_path=str(python_workspace),
        )
        assert "pyproject.toml" in result

    def test_focus_directory(self, python_workspace):
        """Focus vao subdirectory cu the."""
        result = explain_architecture(
            workspace_path=str(python_workspace),
            focus_directory="auth",
        )
        assert "Error" not in result
        assert "focus: auth/" in result

    def test_invalid_focus_directory(self, python_workspace):
        """Focus directory khong ton tai -> Error."""
        result = explain_architecture(
            workspace_path=str(python_workspace),
            focus_directory="nonexistent",
        )
        assert "Error" in result

    def test_invalid_workspace(self):
        """Workspace khong hop le -> Error."""
        result = explain_architecture(
            workspace_path="/nonexistent/path",
        )
        assert "Error" in result

    def test_suggested_exploration_order(self, python_workspace):
        """Output chua goi y thu tu kham pha."""
        result = explain_architecture(
            workspace_path=str(python_workspace),
        )
        assert "Suggested exploration order" in result

    def test_detects_entry_points(self, python_workspace):
        """Phat hien entry points (main.py, server.py, etc.)."""
        result = explain_architecture(
            workspace_path=str(python_workspace),
        )
        assert "Entry Points" in result
        assert "main.py" in result

    def test_shows_file_count(self, python_workspace):
        """Hien thi tong so files."""
        result = explain_architecture(
            workspace_path=str(python_workspace),
        )
        assert "Total:" in result
        assert "files" in result

    def test_js_workspace_detects_package_json(self, js_workspace):
        """Nhan dien package.json la config file."""
        result = explain_architecture(
            workspace_path=str(js_workspace),
        )
        assert "package.json" in result

    def test_empty_workspace(self, empty_workspace):
        """Workspace voi chi README.md -> van chay duoc."""
        result = explain_architecture(
            workspace_path=str(empty_workspace),
        )
        # Co the bao khong co files hoac tra ve summary toi gian
        assert "Error" not in result or "No files" in result
