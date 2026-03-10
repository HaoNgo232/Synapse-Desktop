"""
Test Analyzer - Phan tich test coverage gaps trong codebase.

Chuc nang:
1. Tim test files tuong ung cho source files
2. Extract symbols da co test (test function -> source symbol mapping)
3. Xac dinh symbols chua duoc test (coverage gaps)
4. Phan loai muc uu tien test (public API > private helpers)
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from domain.codemap.symbol_extractor import extract_symbols
from domain.codemap.types import Symbol, SymbolKind

logger = logging.getLogger(__name__)

# Cac naming convention de tim test files
_PYTHON_TEST_PATTERNS = ["test_{name}.py", "{name}_test.py"]
_JS_TS_TEST_PATTERNS = [
    "{name}.test.{ext}",
    "{name}.spec.{ext}",
]


class TestPriority:
    """Muc do uu tien khi viet test cho symbol."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class CoverageResult:
    """
    Ket qua phan tich test coverage cho mot source file.

    Attributes:
        source_file: Relative path cua source file
        test_files: Danh sach test files tuong ung da tim duoc
        tested_symbols: Symbols da co test (ten -> test functions tuong ung)
        untested_symbols: Symbols chua co test
        coverage_pct: Phan tram symbols da co test
        priority_symbols: Symbols uu tien cao can test truoc
    """

    source_file: str = ""
    test_files: List[str] = field(default_factory=list)
    tested_symbols: Dict[str, List[str]] = field(default_factory=dict)
    untested_symbols: List[Symbol] = field(default_factory=list)
    coverage_pct: float = 0.0
    priority_symbols: List[Symbol] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """
    Ket qua phan tich toan bo cho rp_test workflow.

    Attributes:
        file_coverages: Coverage analysis cho tung source file
        existing_test_files: Test files da tim duoc trong workspace
        suggested_test_files: Test files moi can tao
        total_symbols: Tong symbols trong scope
        total_untested: Tong symbols chua co test
        analysis_summary: Tom tat dang text
    """

    file_coverages: List[CoverageResult] = field(default_factory=list)
    existing_test_files: List[str] = field(default_factory=list)
    suggested_test_files: List[str] = field(default_factory=list)
    total_symbols: int = 0
    total_untested: int = 0
    analysis_summary: str = ""


def find_test_files(workspace_path: Path, source_file_rel: str) -> List[str]:
    """
    Tim test files tuong ung voi source file theo naming convention.

    Ho tro ca Python (test_*.py, *_test.py) va JS/TS (*.test.ts, *.spec.ts).
    Uu tien test file gan nhat trong directory hierarchy.

    Args:
        workspace_path: Workspace root directory
        source_file_rel: Relative path cua source file (vi du: "auth/login.py")

    Returns:
        Danh sach relative paths cua cac test files tim duoc
    """
    source_path = Path(source_file_rel)
    stem = source_path.stem  # "login"
    ext = source_path.suffix  # ".py"
    parent = source_path.parent  # "auth"

    candidates: List[str] = []

    if ext == ".py":
        # Python naming conventions
        search_dirs = [
            Path("tests") / parent,  # tests/auth/test_login.py
            Path("tests"),  # tests/test_login.py
            parent,  # auth/test_login.py
            Path("test_" + str(parent)) if str(parent) != "." else None,
        ]

        for search_dir in search_dirs:
            if search_dir is None:
                continue
            for pattern in _PYTHON_TEST_PATTERNS:
                test_name = pattern.format(name=stem)
                test_path = search_dir / test_name
                test_full = workspace_path / test_path
                if test_full.is_file():
                    candidates.append(test_path.as_posix())

    elif ext in (".js", ".ts", ".jsx", ".tsx"):
        # JS/TS naming conventions
        raw_ext = ext.lstrip(".")
        search_dirs = [
            parent,  # src/utils.test.ts
            Path("tests") / parent,  # tests/src/utils.test.ts
            Path("tests"),  # tests/utils.test.ts
            Path("__tests__"),  # __tests__/utils.test.ts
            Path("__tests__") / parent,
        ]

        for search_dir in search_dirs:
            for pattern in _JS_TS_TEST_PATTERNS:
                test_name = pattern.format(name=stem, ext=raw_ext)
                test_path = search_dir / test_name
                test_full = workspace_path / test_path
                if test_full.is_file():
                    candidates.append(test_path.as_posix())

    # Loai bo duplicates, giu thu tu uu tien
    seen: Set[str] = set()
    unique: List[str] = []
    for c in candidates:
        normalized = os.path.normpath(c)
        if normalized not in seen:
            seen.add(normalized)
            unique.append(c)

    return unique


def analyze_test_coverage(
    workspace_path: Path, source_files: List[str]
) -> AnalysisResult:
    """
    Phan tich test coverage cho danh sach source files.

    Cho moi source file:
    1. Extract symbols (functions, classes, methods)
    2. Tim test files tuong ung
    3. So sanh de xac dinh coverage gaps
    4. Phan loai symbols theo muc uu tien

    Args:
        workspace_path: Workspace root directory
        source_files: Danh sach relative paths cua source files

    Returns:
        TestAnalysisResult voi thong tin coverage toan bo
    """
    result = AnalysisResult()
    all_existing_tests: Set[str] = set()
    all_suggested_tests: Set[str] = set()

    for source_rel in source_files:
        source_full = workspace_path / source_rel
        if not source_full.is_file():
            continue

        coverage = CoverageResult(source_file=source_rel)

        # Buoc 1: Extract symbols tu source file
        try:
            content = source_full.read_text(encoding="utf-8", errors="ignore")
            source_symbols = extract_symbols(str(source_full), content)
        except Exception:
            logger.debug("Khong the parse source file: %s", source_rel)
            result.file_coverages.append(coverage)
            continue

        # Chi lay functions, classes, methods (bo qua imports va variables)
        testable_symbols = [
            s
            for s in source_symbols
            if s.kind in (SymbolKind.FUNCTION, SymbolKind.CLASS, SymbolKind.METHOD)
        ]

        if not testable_symbols:
            result.file_coverages.append(coverage)
            continue

        # Buoc 2: Tim test files tuong ung
        test_files = find_test_files(workspace_path, source_rel)
        coverage.test_files = test_files
        all_existing_tests.update(test_files)

        # Buoc 3: Extract test symbols va match voi source symbols (usage-aware)
        test_symbol_names: Set[str] = set()
        for test_rel in test_files:
            test_full = workspace_path / test_rel
            try:
                test_content = test_full.read_text(encoding="utf-8", errors="ignore")
                test_symbols = extract_symbols(str(test_full), test_content)
                for ts in test_symbols:
                    if ts.kind in (SymbolKind.FUNCTION, SymbolKind.METHOD):
                        test_symbol_names.add(ts.name)
            except Exception:
                logger.debug("Khong the parse test file: %s", test_rel)

        # Buoc 4: Match test functions voi source symbols (usage-aware)
        from domain.workflow.shared.usage_aware_test_matcher import (
            match_tests_to_source_usage_aware,
        )

        tested: Dict[str, List[str]] = {}
        untested: List[Symbol] = []

        for sym in testable_symbols:
            # Use usage-aware matcher
            matching_test_files = match_tests_to_source_usage_aware(
                workspace_path, source_rel, sym.name, test_files
            )
            if matching_test_files:
                tested[sym.name] = matching_test_files
            else:
                untested.append(sym)

        coverage.tested_symbols = tested
        coverage.untested_symbols = untested

        # Buoc 5: Tinh coverage va xac dinh priority
        total = len(testable_symbols)
        tested_count = len(tested)
        coverage.coverage_pct = (tested_count / total * 100) if total > 0 else 0.0

        coverage.priority_symbols = [
            s for s in untested if _classify_priority(s) == TestPriority.HIGH
        ]

        result.file_coverages.append(coverage)
        result.total_symbols += total
        result.total_untested += len(untested)

        # Suggest test file neu chua co
        if not test_files:
            suggested = suggest_test_file_path(workspace_path, source_rel)
            if suggested:
                all_suggested_tests.add(suggested)

    result.existing_test_files = sorted(all_existing_tests)
    result.suggested_test_files = sorted(all_suggested_tests)

    # Tao summary
    overall_pct = (
        ((result.total_symbols - result.total_untested) / result.total_symbols * 100)
        if result.total_symbols > 0
        else 0.0
    )
    result.analysis_summary = (
        f"{result.total_symbols - result.total_untested}/{result.total_symbols} "
        f"symbols tested ({overall_pct:.0f}%). "
        f"{result.total_untested} symbols need tests."
    )

    return result


def _match_test_to_source(source_symbol: Symbol, test_names: Set[str]) -> List[str]:
    """
    Heuristic matching: tim test functions tuong ung voi source symbol.

    Vi du:
    - test_login -> matches "login"
    - test_LoginService_authenticate -> matches "LoginService" hoac "authenticate"
    - TestLogin.test_valid -> matches "Login" hoac "login"

    Args:
        source_symbol: Symbol can tim test tuong ung
        test_names: Tap hop ten cac test functions

    Returns:
        Danh sach ten test functions match duoc
    """
    matches: List[str] = []
    sym_name_lower = source_symbol.name.lower()

    for test_name in test_names:
        test_lower = test_name.lower()

        # Bo prefix "test_" de lay phan ten thuc
        clean_test = test_lower
        if clean_test.startswith("test_"):
            clean_test = clean_test[5:]
        elif clean_test.startswith("test"):
            clean_test = clean_test[4:]

        # Match truc tiep: test_login -> login
        if clean_test == sym_name_lower:
            matches.append(test_name)
            continue

        # Match bat dau: test_login_valid_credentials -> login
        if clean_test.startswith(sym_name_lower + "_"):
            matches.append(test_name)
            continue
        if clean_test.startswith(sym_name_lower):
            matches.append(test_name)
            continue

        # Match chua ten: test_should_validate_input -> validate_input
        if sym_name_lower in clean_test:
            matches.append(test_name)
            continue

    return matches


def _classify_priority(symbol: Symbol) -> str:
    """
    Phan loai muc uu tien khi viet test cho symbol.

    - HIGH: Public functions/classes (khong bat dau bang "_")
    - MEDIUM: Protected methods ("_single_underscore")
    - LOW: Private methods ("__double_underscore"), internal helpers

    Args:
        symbol: Symbol can phan loai

    Returns:
        Muc uu tien (HIGH, MEDIUM, LOW)
    """
    name = symbol.name

    # Dunder methods (__init__, __str__, etc.) -> LOW
    if name.startswith("__") and name.endswith("__"):
        return TestPriority.LOW

    # Private methods (__name) -> LOW
    if name.startswith("__"):
        return TestPriority.LOW

    # Protected methods (_name) -> MEDIUM
    if name.startswith("_"):
        return TestPriority.MEDIUM

    # Public API -> HIGH
    return TestPriority.HIGH


def suggest_test_file_path(workspace_path: Path, source_file_rel: str) -> Optional[str]:
    """
    Goi y duong dan cho test file moi.

    - Python: tests/test_{module}.py hoac tests/{package}/test_{module}.py
    - JS/TS: {source_dir}/{name}.test.{ext}

    Args:
        workspace_path: Workspace root directory
        source_file_rel: Relative path cua source file

    Returns:
        Suggested relative path cho test file, hoac None
    """
    source_path = Path(source_file_rel)
    stem = source_path.stem
    ext = source_path.suffix
    parent = source_path.parent

    if ext == ".py":
        # Uu tien tests/ directory co san
        tests_dir = workspace_path / "tests"
        if tests_dir.is_dir():
            if str(parent) != ".":
                return f"tests/{parent}/test_{stem}.py"
            return f"tests/test_{stem}.py"
        # Fallback: tao tests/ directory moi
        return f"tests/test_{stem}.py"

    elif ext in (".js", ".ts", ".jsx", ".tsx"):
        raw_ext = ext.lstrip(".")
        return f"{parent}/{stem}.test.{raw_ext}"

    return None


def detect_test_framework(workspace_path: Path) -> str:
    """
    Tu dong nhan dien test framework tu project config.

    Kiem tra pyproject.toml, setup.cfg, package.json, etc.

    Args:
        workspace_path: Workspace root directory

    Returns:
        Ten framework ("pytest", "jest", "vitest", "unittest", "mocha")
    """
    # Python: kiem tra pyproject.toml
    pyproject = workspace_path / "pyproject.toml"
    if pyproject.is_file():
        try:
            content = pyproject.read_text(encoding="utf-8", errors="ignore")
            if "pytest" in content.lower():
                return "pytest"
            if "unittest" in content.lower():
                return "unittest"
        except Exception:
            pass

    # Python: kiem tra setup.cfg
    setup_cfg = workspace_path / "setup.cfg"
    if setup_cfg.is_file():
        try:
            content = setup_cfg.read_text(encoding="utf-8", errors="ignore")
            if "pytest" in content.lower():
                return "pytest"
        except Exception:
            pass

    # JS/TS: kiem tra package.json
    package_json = workspace_path / "package.json"
    if package_json.is_file():
        try:
            content = package_json.read_text(encoding="utf-8", errors="ignore")
            if "vitest" in content:
                return "vitest"
            if "jest" in content:
                return "jest"
            if "mocha" in content:
                return "mocha"
        except Exception:
            pass

    # Fallback dua tren file types ton tai
    py_files = list(workspace_path.rglob("*.py"))
    if py_files:
        return "pytest"

    js_files = list(workspace_path.rglob("*.ts")) + list(workspace_path.rglob("*.js"))
    if js_files:
        return "jest"

    return "pytest"


def format_test_analysis_xml(analysis: AnalysisResult) -> str:
    """
    Render TestAnalysisResult thanh XML section de nhung vao handoff prompt.

    Args:
        analysis: Ket qua phan tich test coverage

    Returns:
        Chuoi XML san sang de nhung vao extra_sections cua HandoffContext
    """
    lines: List[str] = []

    # Coverage summary
    lines.append("<coverage_summary>")
    lines.append(f"  Total symbols: {analysis.total_symbols}")
    tested = analysis.total_symbols - analysis.total_untested
    pct = (tested / analysis.total_symbols * 100) if analysis.total_symbols > 0 else 0
    lines.append(f"  Tested: {tested} ({pct:.0f}%)")
    lines.append(f"  Untested: {analysis.total_untested} ({100 - pct:.0f}%)")
    lines.append("</coverage_summary>")
    lines.append("")

    # Untested symbols (danh sach chi tiet)
    lines.append("<untested_symbols>")
    for cov in analysis.file_coverages:
        for sym in cov.untested_symbols:
            priority = _classify_priority(sym)
            sig = f' signature="{sym.signature}"' if sym.signature else ""
            parent = f' parent="{sym.parent}"' if sym.parent else ""
            lines.append(
                f'  <symbol name="{sym.name}" kind="{sym.kind.value}" '
                f'file="{cov.source_file}" line="{sym.line_start}" '
                f'priority="{priority}"{sig}{parent}/>'
            )
    lines.append("</untested_symbols>")
    lines.append("")

    # Existing test files
    if analysis.existing_test_files:
        lines.append("<existing_tests>")
        for tf in analysis.existing_test_files:
            lines.append(f'  <test_file path="{tf}"/>')
        lines.append("</existing_tests>")
        lines.append("")

    # Suggested new test files
    if analysis.suggested_test_files:
        lines.append("<suggested_files>")
        for sf in analysis.suggested_test_files:
            lines.append(f'  <file path="{sf}"/>')
        lines.append("</suggested_files>")

    return "\n".join(lines)
