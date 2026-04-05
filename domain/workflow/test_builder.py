"""
Test Builder Workflow - Chuan bi context toi uu cho AI viet tests.

Workflow:
1. Nhan source file paths (hoac git diff) tu user
2. Detect scope: source files + dependencies
3. Phan tich test coverage gaps
4. Thu thap existing tests + source code + dependencies
5. Optimize content to fit token budget
6. Tao handoff prompt voi test-specific instructions
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from domain.workflow.shared.scope_detector import detect_scope_from_file_paths
from domain.workflow.shared.token_budget_manager import TokenBudgetManager
from domain.workflow.shared.handoff_formatter import (
    HandoffContext,
    format_handoff_xml,
    format_relationships_section,
)
from domain.prompt.generator import generate_file_map
from domain.codemap.graph_builder import CodeMapBuilder
from infrastructure.filesystem.file_utils import scan_directory
from domain.workflow.test_analyzer import (
    AnalysisResult,
    analyze_test_coverage,
    detect_test_framework,
    format_test_analysis_xml,
    TestPriority,
    classify_priority,
)
from application.services.tokenization_service import TokenizationService
from domain.errors import DomainValidationError

logger = logging.getLogger(__name__)


def _empty_str_list() -> List[str]:
    """Tao list rong co typing ro rang cho dataclass factories."""
    return []


# Template huong dan AI viet tests
TEST_ACTION_INSTRUCTIONS_TEMPLATE = """## Task: Write Tests

### Coverage Analysis
{coverage_summary}

### Untested Symbols (Priority Order)
{untested_symbols_list}

### Test Framework: {test_framework}

### Instructions
1. Write tests for each untested symbol listed above, prioritizing HIGH priority items.
2. Follow the patterns and conventions from existing test files included in the context.
3. For each function/method, cover:
   - Happy path (normal inputs -> expected outputs)
   - Edge cases (empty input, None, boundary values)
   - Error handling (invalid inputs -> appropriate exceptions)
4. Use descriptive test names: test_{{function_name}}_{{scenario}}_{{expected_result}}
5. Mock external dependencies (database, API calls, file I/O) appropriately.
6. If existing test files are provided, maintain consistency in:
   - Import style and fixture patterns
   - Assertion style (assert vs assertEqual vs expect)
   - Test organization (class-based vs function-based)

### Suggested Test File Locations
{suggested_test_files}
"""


@dataclass
class BuildTestResult:
    """
    Ket qua cua Test Builder workflow.

    Attributes:
        prompt: Prompt hoan chinh (XML format)
        total_tokens: Tong tokens cua prompt
        files_included: So files duoc include
        files_sliced: So files bi cat
        files_smart_only: So files chi co signatures
        scope_summary: Tom tat scope detection
        coverage_summary: Tom tat test coverage
        untested_symbols: So symbols chua co test
        suggested_test_files: Danh sach test files can tao
        optimizations: Danh sach cac buoc toi uu da ap dung
    """

    prompt: str = ""
    total_tokens: int = 0
    files_included: int = 0
    files_sliced: int = 0
    files_smart_only: int = 0
    scope_summary: str = ""
    coverage_summary: str = ""
    untested_symbols: int = 0
    suggested_test_files: List[str] = field(default_factory=_empty_str_list)
    optimizations: List[str] = field(default_factory=_empty_str_list)


def run_test_builder(
    workspace_path: str,
    task_description: str = "Write tests for the specified files",
    file_paths: Optional[List[str]] = None,
    max_tokens: int = 100_000,
    test_framework: Optional[str] = None,
    include_existing_tests: bool = True,
    include_git_changes: bool = False,
    output_file: Optional[str] = None,
    tokenization_service: Optional[TokenizationService] = None,
) -> BuildTestResult:
    """
    Chay Test Builder workflow.

    Phan tich source files, tim coverage gaps, thu thap context,
    va tao prompt toi uu cho AI viet tests.

    Args:
        workspace_path: Absolute path to workspace root
        task_description: Mo ta task (vi du: "Write tests for auth module")
        file_paths: Optional danh sach relative paths cua source files
        max_tokens: Token budget toi da (default 100k)
        test_framework: Test framework ("pytest", "jest", etc.). None = auto-detect
        include_existing_tests: Co include existing test files lam reference khong
        include_git_changes: Co bao gom git diffs khong
        output_file: Optional path de ghi prompt ra file
        tokenization_service: Optional TokenizationService (inject)

    Returns:
        BuildTestResult voi prompt va metadata
    """
    ws = Path(workspace_path).resolve()
    if not ws.is_dir():
        raise DomainValidationError(f"'{workspace_path}' is not a valid directory")

    # Validate output_file - chong path traversal
    if output_file:
        out_path = (ws / output_file).resolve()
        if not out_path.is_relative_to(ws):
            raise DomainValidationError("output_file path traversal detected")

    # Initialize tokenization service
    tok_service = tokenization_service or TokenizationService()

    # Buoc 1: Detect scope - tim source files va dependencies
    if not file_paths:
        file_paths = []

    scope = detect_scope_from_file_paths(ws, file_paths, max_depth=2)

    if not scope.primary_files:
        return BuildTestResult(
            prompt="[Error: No files detected in scope]",
            scope_summary="No files found",
        )

    # Buoc 2: Phan tich test coverage gaps
    analysis = analyze_test_coverage(ws, scope.primary_files)

    # Buoc 3: Auto-detect test framework neu chua chi dinh
    framework = test_framework or detect_test_framework(ws)

    # Buoc 4: Build file map
    from domain.filesystem.ignore_engine import IgnoreEngine

    ignore_engine = IgnoreEngine()
    tree = scan_directory(ws, ignore_engine)

    # Tap hop tat ca files can hien thi trong map
    all_relevant_paths = set(
        str(ws / p)
        for p in (
            scope.primary_files + scope.dependency_files + analysis.existing_test_files
        )
    )
    file_map = generate_file_map(tree, all_relevant_paths, workspace_root=ws)

    # Buoc 5: Optimize content de fit vao token budget
    codemap_builder = CodeMapBuilder(ws)
    for p in all_relevant_paths:
        codemap_builder.build_for_file(str(p))

    budget_mgr = TokenBudgetManager(tok_service, max_tokens, codemap_builder)

    # Primary files = source files can test + existing test files (de AI hoc pattern)
    primary_paths = [ws / p for p in scope.primary_files]
    if include_existing_tests:
        for test_rel in analysis.existing_test_files:
            test_path = ws / test_rel
            if test_path.is_file() and test_path not in primary_paths:
                primary_paths.append(test_path)

    dep_paths = [ws / p for p in scope.dependency_files]

    # Dung untested symbols lam hint de file_slicer giu lai phan quan trong
    relevant_symbols = dict(scope.relevant_symbols)
    for cov in analysis.file_coverages:
        if cov.untested_symbols:
            sym_names = {s.name for s in cov.untested_symbols}
            if cov.source_file in relevant_symbols:
                relevant_symbols[cov.source_file].update(sym_names)
            else:
                relevant_symbols[cov.source_file] = sym_names

    budget_result = budget_mgr.fit_files_to_budget(
        primary_files=primary_paths,
        dependency_files=dep_paths,
        instructions=task_description,
        workspace_root=ws,
        relevant_symbols=relevant_symbols,
    )

    # Buoc 6: Build relationships section
    relationships = format_relationships_section(
        ws, scope.primary_files + scope.dependency_files
    )

    # Buoc 7: Tao test-specific action instructions
    action_instructions = _build_action_instructions(analysis, framework)

    # Tao XML section cho test analysis
    test_analysis_xml = format_test_analysis_xml(analysis)

    # Assemble handoff prompt
    context = HandoffContext(
        task_description=task_description,
        file_contents=budget_result.file_contents,
        file_map=file_map,
        relationships=relationships,
        action_instructions=action_instructions,
        metadata={
            "total_tokens": budget_result.total_tokens,
            "files_included": len(budget_result.file_contents),
            "files_sliced": len(budget_result.files_sliced),
            "files_smartified": len(budget_result.files_smartified),
            "optimizations": ", ".join(budget_result.optimizations_applied),
            "test_framework": framework,
            "coverage_pct": f"{_calc_overall_pct(analysis):.0f}%",
        },
        extra_sections={"test_analysis": test_analysis_xml},
    )

    # Inject contract pack vào extra_sections
    from domain.workflow.shared.contract_injector import inject_contract_pack_to_handoff

    inject_contract_pack_to_handoff(context, ws)

    prompt = format_handoff_xml(context)

    # Ghi ra file neu duoc yeu cau
    if output_file:
        out_path = (ws / output_file).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(prompt, encoding="utf-8")

    # Build result
    scope_summary = (
        f"{len(scope.primary_files)} primary, "
        f"{len(scope.dependency_files)} dependencies"
    )

    return BuildTestResult(
        prompt=prompt,
        total_tokens=budget_result.total_tokens,
        files_included=len(budget_result.file_contents),
        files_sliced=len(budget_result.files_sliced),
        files_smart_only=len(budget_result.files_smartified),
        scope_summary=scope_summary,
        coverage_summary=analysis.analysis_summary,
        untested_symbols=analysis.total_untested,
        suggested_test_files=analysis.suggested_test_files,
        optimizations=budget_result.optimizations_applied,
    )


def _build_action_instructions(
    analysis: AnalysisResult,
    test_framework: str,
) -> str:
    """
    Tao action instructions huong dan AI viet tests.

    Dien thong tin tu TestAnalysisResult vao template.

    Args:
        analysis: Ket qua phan tich test coverage
        test_framework: Framework duoc chon (pytest, jest, etc.)

    Returns:
        Action instructions dang text
    """
    # Build danh sach untested symbols theo thu tu priority
    untested_lines: List[str] = []
    for cov in analysis.file_coverages:
        # Sap xep: HIGH truoc, LOW cuoi
        priority_order = {
            TestPriority.HIGH: 0,
            TestPriority.MEDIUM: 1,
            TestPriority.LOW: 2,
        }
        sorted_symbols = sorted(
            cov.untested_symbols,
            key=lambda s: priority_order.get(classify_priority(s), 3),
        )
        for sym in sorted_symbols:
            priority = classify_priority(sym)
            sig = sym.signature or sym.name
            untested_lines.append(
                f"- [{priority}] {cov.source_file}: {sig} (line {sym.line_start})"
            )

    # Build danh sach suggested test files
    suggested_lines: List[str] = []
    if analysis.suggested_test_files:
        for sf in analysis.suggested_test_files:
            suggested_lines.append(f"- {sf}")
    else:
        suggested_lines.append("- (All source files already have test files)")

    return TEST_ACTION_INSTRUCTIONS_TEMPLATE.format(
        coverage_summary=analysis.analysis_summary,
        untested_symbols_list=(
            "\n".join(untested_lines)
            if untested_lines
            else "- (All symbols are tested)"
        ),
        test_framework=test_framework,
        suggested_test_files="\n".join(suggested_lines),
    )


def _calc_overall_pct(analysis: AnalysisResult) -> float:
    """
    Tinh phan tram coverage tong the.

    Args:
        analysis: Ket qua phan tich test coverage

    Returns:
        Phan tram coverage (0-100)
    """
    if analysis.total_symbols == 0:
        return 0.0
    tested = analysis.total_symbols - analysis.total_untested
    return tested / analysis.total_symbols * 100
