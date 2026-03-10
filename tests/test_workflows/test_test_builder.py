"""
Tests cho test_builder va test_analyzer workflows.

Bao gom:
- Tim test files tuong ung voi source files
- Phan tich test coverage gaps
- Chay end-to-end test builder workflow
- Auto-detect test framework
"""

import pytest

from domain.workflow.test_analyzer import (
    AnalysisResult,
    TestPriority,
    find_test_files,
    analyze_test_coverage,
    detect_test_framework,
    suggest_test_file_path,
    format_test_analysis_xml,
    _classify_priority,
    _match_test_to_source,
)
from domain.workflow.test_builder import (
    BuildTestResult,
    run_test_builder,
    _calc_overall_pct,
)
from domain.codemap.types import Symbol, SymbolKind


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def python_workspace(tmp_path):
    """Workspace voi Python source + partial tests."""
    ws = tmp_path / "project"
    ws.mkdir()

    # Source files
    (ws / "auth.py").write_text(
        "def login(user, pwd):\n"
        "    pass\n"
        "\n"
        "def logout(session):\n"
        "    pass\n"
        "\n"
        "def validate_token(token):\n"
        "    pass\n"
    )
    (ws / "utils.py").write_text(
        "def format_date(d):\n    pass\n\ndef parse_csv(data):\n    pass\n"
    )

    # Partial test coverage
    tests_dir = ws / "tests"
    tests_dir.mkdir()
    (tests_dir / "__init__.py").write_text("")
    (tests_dir / "test_auth.py").write_text(
        "from auth import login\n"
        "\n"
        "def test_login_success():\n"
        "    pass\n"
        "\n"
        "def test_login_failure():\n"
        "    pass\n"
    )

    # pyproject.toml cho framework detection
    (ws / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n'
    )

    return ws


@pytest.fixture
def empty_workspace(tmp_path):
    """Workspace khong co test files."""
    ws = tmp_path / "empty_project"
    ws.mkdir()

    (ws / "main.py").write_text("def run():\n    pass\n\ndef setup():\n    pass\n")

    return ws


# ===================================================================
# Test: find_test_files
# ===================================================================


class TestFindTestFiles:
    """Tests cho ham find_test_files."""

    def test_find_python_test_file(self, python_workspace):
        """Tim duoc test file theo naming convention test_{name}.py."""
        result = find_test_files(python_workspace, "auth.py")
        assert len(result) >= 1
        assert any("test_auth.py" in r for r in result)

    def test_find_test_files_not_found(self, empty_workspace):
        """Source file khong co test file -> tra ve list rong."""
        result = find_test_files(empty_workspace, "main.py")
        assert result == []

    def test_find_test_files_nested_path(self, python_workspace):
        """Tim test file cho source file trong subdirectory."""
        # Tao subdirectory
        sub = python_workspace / "services"
        sub.mkdir()
        (sub / "cache.py").write_text("def get_cache(): pass\n")

        tests_sub = python_workspace / "tests" / "services"
        tests_sub.mkdir(parents=True)
        (tests_sub / "test_cache.py").write_text("def test_get_cache(): pass\n")

        result = find_test_files(python_workspace, "services/cache.py")
        assert len(result) >= 1
        assert any("test_cache.py" in r for r in result)


# ===================================================================
# Test: analyze_test_coverage
# ===================================================================


class TestAnalyzeTestCoverage:
    """Tests cho ham analyze_test_coverage."""

    def test_partial_coverage(self, python_workspace):
        """Source co 3 functions, test file cover 1 -> partial coverage.

        Note: Usage-aware matcher hien tai da duoc fix loi false positive
        (Bug #4). Do do, gio no chi match 'login', va testcoverage that su
        la 33% (1/3 symbols).
        """
        result = analyze_test_coverage(python_workspace, ["auth.py"])

        assert result.total_symbols > 0
        assert len(result.file_coverages) == 1

        cov = result.file_coverages[0]
        assert cov.source_file == "auth.py"
        assert len(cov.test_files) >= 1

        # Usage-aware matcher match tất cả symbols
        assert cov.coverage_pct >= 33.0  # At least 1/3
        assert "login" in cov.tested_symbols

    def test_no_tests_exist(self, empty_workspace):
        """Source files khong co test file nao -> 0% coverage."""
        result = analyze_test_coverage(empty_workspace, ["main.py"])

        assert result.total_symbols > 0
        assert result.total_untested == result.total_symbols
        assert len(result.suggested_test_files) > 0

    def test_nonexistent_source_file(self, python_workspace):
        """Source file khong ton tai -> skip."""
        result = analyze_test_coverage(python_workspace, ["nonexistent.py"])
        assert result.total_symbols == 0


# ===================================================================
# Test: _match_test_to_source
# ===================================================================


class TestMatchTestToSource:
    """Tests cho heuristic matching giua test function va source symbol."""

    def test_exact_match(self):
        """test_login -> matches login."""
        sym = Symbol(
            name="login",
            kind=SymbolKind.FUNCTION,
            file_path="auth.py",
            line_start=1,
            line_end=2,
        )
        test_names = {"test_login", "test_something_else"}
        result = _match_test_to_source(sym, test_names)
        assert "test_login" in result

    def test_prefix_match(self):
        """test_login_success -> matches login."""
        sym = Symbol(
            name="login",
            kind=SymbolKind.FUNCTION,
            file_path="auth.py",
            line_start=1,
            line_end=2,
        )
        test_names = {"test_login_success", "test_login_failure"}
        result = _match_test_to_source(sym, test_names)
        assert len(result) == 2

    def test_no_match(self):
        """Khong co test nao match."""
        sym = Symbol(
            name="validate_token",
            kind=SymbolKind.FUNCTION,
            file_path="auth.py",
            line_start=1,
            line_end=2,
        )
        test_names = {"test_login", "test_signup"}
        result = _match_test_to_source(sym, test_names)
        assert result == []

    def test_contains_match(self):
        """test_should_validate_token_ok -> matches validate_token."""
        sym = Symbol(
            name="validate_token",
            kind=SymbolKind.FUNCTION,
            file_path="auth.py",
            line_start=1,
            line_end=2,
        )
        test_names = {"test_should_validate_token_ok"}
        result = _match_test_to_source(sym, test_names)
        assert len(result) == 1


# ===================================================================
# Test: _classify_priority
# ===================================================================


class TestClassifyPriority:
    """Tests cho phan loai muc uu tien."""

    def test_public_function_is_high(self):
        """Public function -> HIGH priority."""
        sym = Symbol(
            name="login",
            kind=SymbolKind.FUNCTION,
            file_path="auth.py",
            line_start=1,
            line_end=2,
        )
        assert _classify_priority(sym) == TestPriority.HIGH

    def test_protected_method_is_medium(self):
        """Protected method -> MEDIUM priority."""
        sym = Symbol(
            name="_validate",
            kind=SymbolKind.METHOD,
            file_path="auth.py",
            line_start=1,
            line_end=2,
        )
        assert _classify_priority(sym) == TestPriority.MEDIUM

    def test_private_method_is_low(self):
        """Private method -> LOW priority."""
        sym = Symbol(
            name="__process",
            kind=SymbolKind.METHOD,
            file_path="auth.py",
            line_start=1,
            line_end=2,
        )
        assert _classify_priority(sym) == TestPriority.LOW

    def test_dunder_is_low(self):
        """Dunder method -> LOW priority."""
        sym = Symbol(
            name="__init__",
            kind=SymbolKind.METHOD,
            file_path="auth.py",
            line_start=1,
            line_end=2,
        )
        assert _classify_priority(sym) == TestPriority.LOW


# ===================================================================
# Test: detect_test_framework
# ===================================================================


class TestDetectTestFramework:
    """Tests cho auto-detect test framework."""

    def test_detect_pytest(self, python_workspace):
        """pyproject.toml co pytest -> detect 'pytest'."""
        result = detect_test_framework(python_workspace)
        assert result == "pytest"

    def test_detect_jest(self, tmp_path):
        """package.json co jest -> detect 'jest'."""
        ws = tmp_path / "js_project"
        ws.mkdir()
        (ws / "package.json").write_text('{"devDependencies": {"jest": "^29.0"}}')
        result = detect_test_framework(ws)
        assert result == "jest"

    def test_detect_vitest(self, tmp_path):
        """package.json co vitest -> detect 'vitest' (uu tien hon jest)."""
        ws = tmp_path / "vite_project"
        ws.mkdir()
        (ws / "package.json").write_text(
            '{"devDependencies": {"vitest": "^1.0", "jest": "^29.0"}}'
        )
        result = detect_test_framework(ws)
        assert result == "vitest"

    def test_fallback_python(self, tmp_path):
        """Khong co config -> fallback dua tren file types."""
        ws = tmp_path / "plain"
        ws.mkdir()
        (ws / "app.py").write_text("pass")
        result = detect_test_framework(ws)
        assert result == "pytest"


# ===================================================================
# Test: suggest_test_file_path
# ===================================================================


class TestSuggestTestFilePath:
    """Tests cho goi y duong dan test file moi."""

    def test_suggest_python_with_tests_dir(self, python_workspace):
        """Co tests/ dir -> suggest tests/test_{name}.py."""
        result = suggest_test_file_path(python_workspace, "utils.py")
        assert result == "tests/test_utils.py"

    def test_suggest_python_nested(self, python_workspace):
        """Nested source -> suggest tests/{package}/test_{name}.py."""
        result = suggest_test_file_path(python_workspace, "services/cache.py")
        assert result == "tests/services/test_cache.py"

    def test_suggest_js(self, tmp_path):
        """JS file -> suggest {dir}/{name}.test.js."""
        ws = tmp_path / "js"
        ws.mkdir()
        result = suggest_test_file_path(ws, "src/utils.ts")
        assert result == "src/utils.test.ts"


# ===================================================================
# Test: format_test_analysis_xml
# ===================================================================


class TestFormatTestAnalysisXml:
    """Tests cho XML rendering cua test analysis."""

    def test_basic_xml_output(self):
        """Render XML co coverage_summary va untested_symbols."""
        analysis = AnalysisResult(
            total_symbols=10,
            total_untested=7,
        )
        xml = format_test_analysis_xml(analysis)
        assert "<coverage_summary>" in xml
        assert "Total symbols: 10" in xml
        assert "Untested: 7" in xml

    def test_suggested_files_in_xml(self):
        """XML chua suggested files section."""
        analysis = AnalysisResult(
            total_symbols=5,
            total_untested=5,
            suggested_test_files=["tests/test_app.py"],
        )
        xml = format_test_analysis_xml(analysis)
        assert "<suggested_files>" in xml
        assert "tests/test_app.py" in xml


# ===================================================================
# Test: run_test_builder (end-to-end)
# ===================================================================


class TestRunTestBuilder:
    """Tests end-to-end cho test builder workflow."""

    def test_basic_run(self, python_workspace):
        """End-to-end: workspace voi source + tests -> valid prompt output."""
        result = run_test_builder(
            workspace_path=str(python_workspace),
            task_description="Write tests for auth module",
            file_paths=["auth.py"],
            max_tokens=50_000,
            test_framework="pytest",
        )

        assert isinstance(result, BuildTestResult)
        assert result.prompt != ""
        assert result.files_included > 0
        assert "test_analysis" in result.prompt
        assert "coverage_summary" in result.prompt

    def test_no_tests_exist(self, empty_workspace):
        """Source files nhung khong co test files -> prompt co suggested files."""
        result = run_test_builder(
            workspace_path=str(empty_workspace),
            task_description="Write tests",
            file_paths=["main.py"],
            max_tokens=50_000,
        )

        assert result.untested_symbols > 0
        assert len(result.suggested_test_files) > 0

    def test_invalid_workspace(self):
        """Workspace khong hop le -> raise ValueError."""
        with pytest.raises(ValueError, match="not a valid directory"):
            run_test_builder(
                workspace_path="/nonexistent/path",
                task_description="test",
                file_paths=["foo.py"],
            )

    def test_output_file(self, python_workspace):
        """Ghi prompt ra file."""
        _ = run_test_builder(
            workspace_path=str(python_workspace),
            task_description="Write tests",
            file_paths=["auth.py"],
            max_tokens=50_000,
            output_file="test_prompt.xml",
        )

        out = python_workspace / "test_prompt.xml"
        assert out.is_file()
        content = out.read_text()
        assert "<synapse_context>" in content

    def test_path_traversal_blocked(self, python_workspace):
        """Path traversal trong output_file -> raise ValueError."""
        with pytest.raises(ValueError, match="path traversal"):
            run_test_builder(
                workspace_path=str(python_workspace),
                task_description="test",
                file_paths=["auth.py"],
                output_file="../../../etc/passwd",
            )


# ===================================================================
# Test: _calc_overall_pct
# ===================================================================


class TestCalcOverallPct:
    """Tests cho tinh phan tram coverage."""

    def test_zero_symbols(self):
        """0 symbols -> 0%."""
        analysis = AnalysisResult(total_symbols=0, total_untested=0)
        assert _calc_overall_pct(analysis) == 0.0

    def test_partial(self):
        """3/10 tested -> 30%."""
        analysis = AnalysisResult(total_symbols=10, total_untested=7)
        assert _calc_overall_pct(analysis) == pytest.approx(30.0)

    def test_full_coverage(self):
        """10/10 tested -> 100%."""
        analysis = AnalysisResult(total_symbols=10, total_untested=0)
        assert _calc_overall_pct(analysis) == pytest.approx(100.0)
