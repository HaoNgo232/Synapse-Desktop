"""
Assumption Verifier - Kiem tra gia dinh cua agent bang codebase thuc.

Agent planning thuong gia dinh nhieu dieu, vi du:
- "module A chi duoc dung boi B"
- "public API chua bi external caller dung"
- "doi ten symbol X chi anh huong 3 file"

Tool nay verify tung assumption bang cach quet codebase thuc te.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Literal, Optional

logger = logging.getLogger(__name__)

Verdict = Literal["pass", "fail", "uncertain"]

# Limits for evidence display in reports
MAX_EVIDENCE_DISPLAY = 5
MAX_EVIDENCE_RESULTS = 10


@dataclass
class AssumptionResult:
    """Ket qua verify mot assumption."""

    assumption: str
    verdict: Verdict
    evidence_files: List[str] = field(default_factory=list)
    evidence_symbols: List[str] = field(default_factory=list)
    confidence: float = 0.0
    details: str = ""

    def to_dict(self) -> dict:
        return {
            "assumption": self.assumption,
            "verdict": self.verdict,
            "evidence_files": self.evidence_files,
            "evidence_symbols": self.evidence_symbols,
            "confidence": self.confidence,
            "details": self.details,
        }


@dataclass
class VerificationReport:
    """Bao cao tong hop cua nhieu assumptions."""

    results: List[AssumptionResult] = field(default_factory=list)
    total: int = 0
    passed: int = 0
    failed: int = 0
    uncertain: int = 0

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "uncertain": self.uncertain,
            "results": [r.to_dict() for r in self.results],
        }

    def format_summary(self) -> str:
        """Format thanh summary text."""
        lines = [
            "Assumption Verification Report",
            f"{'=' * 40}",
            f"Total: {self.total} | Pass: {self.passed} | "
            f"Fail: {self.failed} | Uncertain: {self.uncertain}",
            "",
        ]
        for r in self.results:
            icon = {"pass": "✅", "fail": "❌", "uncertain": "❓"}[r.verdict]
            lines.append(f"{icon} [{r.verdict.upper()}] {r.assumption}")
            if r.details:
                lines.append(f"   {r.details}")
            if r.evidence_files:
                lines.append(f"   Evidence files: {', '.join(r.evidence_files[:MAX_EVIDENCE_DISPLAY])}")
            if r.evidence_symbols:
                lines.append(
                    f"   Evidence symbols: {', '.join(r.evidence_symbols[:MAX_EVIDENCE_DISPLAY])}"
                )
            lines.append(f"   Confidence: {r.confidence:.0%}")
            lines.append("")

        return "\n".join(lines)


def verify_assumptions(
    workspace_root: Path,
    assumptions: List[str],
    all_files: Optional[List[str]] = None,
) -> VerificationReport:
    """
    Verify a list of assumptions against the actual codebase.

    Supports assumption patterns:
    - "only used by X": check if symbol/module only has callers in X
    - "not used externally": check if symbol has no external callers
    - "impacts N files": check actual impact count
    - "has test coverage": check if test files exist

    Args:
        workspace_root: Path to workspace root
        assumptions: List of assumption strings
        all_files: Optional pre-collected file list

    Returns:
        VerificationReport with results for each assumption
    """
    report = VerificationReport()
    report.total = len(assumptions)

    if all_files is None:
        try:
            from application.services.workspace_index import collect_files_from_disk

            all_files = collect_files_from_disk(str(workspace_root))
        except Exception:
            all_files = []

    # Convert to relative paths
    root = workspace_root
    rel_files: List[str] = []
    for f in all_files:
        try:
            rel_files.append(str(Path(f).relative_to(root)))
        except ValueError:
            rel_files.append(f)

    for assumption in assumptions:
        result = _verify_single(workspace_root, assumption, rel_files)
        report.results.append(result)
        if result.verdict == "pass":
            report.passed += 1
        elif result.verdict == "fail":
            report.failed += 1
        else:
            report.uncertain += 1

    return report


def _verify_single(
    workspace_root: Path,
    assumption: str,
    rel_files: List[str],
) -> AssumptionResult:
    """Verify mot assumption don le."""
    assumption_lower = assumption.lower()

    try:
        # Pattern: "X only used by Y" / "X chi duoc dung boi Y"
        if "only used by" in assumption_lower or "chi duoc dung boi" in assumption_lower:
            return _verify_usage_scope(workspace_root, assumption, rel_files)

        # Pattern: "not used externally" / "not used outside"
        if "not used external" in assumption_lower or "not used outside" in assumption_lower:
            return _verify_no_external_usage(workspace_root, assumption, rel_files)

        # Pattern: "impacts N files" / "anh huong N file"
        if "impact" in assumption_lower and any(
            c.isdigit() for c in assumption_lower
        ):
            return _verify_impact_count(workspace_root, assumption, rel_files)

        # Pattern: "has test" / "test coverage" / "co test"
        if "test" in assumption_lower and (
            "has" in assumption_lower
            or "coverage" in assumption_lower
            or "co" in assumption_lower
        ):
            return _verify_test_coverage(workspace_root, assumption, rel_files)

        # Cannot parse assumption pattern
        return AssumptionResult(
            assumption=assumption,
            verdict="uncertain",
            confidence=0.0,
            details="Could not determine assumption type. Supported patterns: "
            "'only used by X', 'not used externally', 'impacts N files', "
            "'has test coverage'.",
        )

    except Exception as e:
        logger.warning("Failed to verify assumption '%s': %s", assumption, e)
        return AssumptionResult(
            assumption=assumption,
            verdict="uncertain",
            confidence=0.0,
            details=f"Verification error: {e}",
        )


def _find_references_in_files(
    workspace_root: Path,
    symbol: str,
    rel_files: List[str],
) -> List[str]:
    """Tim cac file chua reference den symbol."""
    found: List[str] = []
    for rel_path in rel_files:
        full_path = workspace_root / rel_path
        if not full_path.is_file():
            continue
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
            if symbol in content:
                found.append(rel_path)
        except (OSError, UnicodeDecodeError):
            continue
    return found


def _extract_symbol_from_assumption(assumption: str) -> str:
    """Try to extract a symbol name from assumption text."""
    import re

    # Try to find quoted symbol: "X" or 'X' or `X`
    match = re.search(r'["\']([^"\']+)["\']', assumption)
    if match:
        return match.group(1)
    match = re.search(r"`([^`]+)`", assumption)
    if match:
        return match.group(1)
    # Try first capitalized word or path-like token
    tokens = assumption.split()
    for t in tokens:
        if "/" in t or "." in t or t[0:1].isupper():
            return t.strip(".,;:()")
    return ""


def _verify_usage_scope(
    workspace_root: Path, assumption: str, rel_files: List[str]
) -> AssumptionResult:
    """Verify 'X only used by Y'."""
    symbol = _extract_symbol_from_assumption(assumption)
    if not symbol:
        return AssumptionResult(
            assumption=assumption,
            verdict="uncertain",
            confidence=0.0,
            details="Could not extract symbol name from assumption.",
        )

    refs = _find_references_in_files(workspace_root, symbol, rel_files)
    # Filter out the definition file itself
    refs_without_def = [f for f in refs if symbol.lower() not in f.lower()]

    if len(refs_without_def) <= 1:
        return AssumptionResult(
            assumption=assumption,
            verdict="pass",
            evidence_files=refs,
            confidence=0.8,
            details=f"'{symbol}' found in {len(refs)} files total.",
        )
    else:
        return AssumptionResult(
            assumption=assumption,
            verdict="fail",
            evidence_files=refs[:MAX_EVIDENCE_RESULTS],
            confidence=0.7,
            details=f"'{symbol}' found in {len(refs)} files, exceeds expected usage scope.",
        )


def _verify_no_external_usage(
    workspace_root: Path, assumption: str, rel_files: List[str]
) -> AssumptionResult:
    """Verify 'X not used externally'."""
    symbol = _extract_symbol_from_assumption(assumption)
    if not symbol:
        return AssumptionResult(
            assumption=assumption,
            verdict="uncertain",
            confidence=0.0,
            details="Could not extract symbol name from assumption.",
        )

    refs = _find_references_in_files(workspace_root, symbol, rel_files)

    if len(refs) <= 1:
        return AssumptionResult(
            assumption=assumption,
            verdict="pass",
            evidence_files=refs,
            confidence=0.8,
            details=f"'{symbol}' only found in {len(refs)} file(s) — no external usage detected.",
        )
    else:
        return AssumptionResult(
            assumption=assumption,
            verdict="fail",
            evidence_files=refs[:MAX_EVIDENCE_RESULTS],
            confidence=0.7,
            details=f"'{symbol}' found in {len(refs)} files — external usage detected.",
        )


def _verify_impact_count(
    workspace_root: Path, assumption: str, rel_files: List[str]
) -> AssumptionResult:
    """Verify 'impacts N files'."""
    import re

    symbol = _extract_symbol_from_assumption(assumption)
    match = re.search(r"(\d+)", assumption)
    expected_count = int(match.group(1)) if match else 0

    if not symbol:
        return AssumptionResult(
            assumption=assumption,
            verdict="uncertain",
            confidence=0.0,
            details="Could not extract symbol name.",
        )

    refs = _find_references_in_files(workspace_root, symbol, rel_files)
    actual_count = len(refs)

    if actual_count <= expected_count:
        return AssumptionResult(
            assumption=assumption,
            verdict="pass",
            evidence_files=refs[:MAX_EVIDENCE_RESULTS],
            confidence=0.8,
            details=f"'{symbol}' found in {actual_count} files, within limit of {expected_count}.",
        )
    else:
        return AssumptionResult(
            assumption=assumption,
            verdict="fail",
            evidence_files=refs[:MAX_EVIDENCE_RESULTS],
            confidence=0.8,
            details=f"'{symbol}' found in {actual_count} files, exceeds limit of {expected_count}.",
        )


def _verify_test_coverage(
    workspace_root: Path, assumption: str, rel_files: List[str]
) -> AssumptionResult:
    """Verify 'has test coverage'."""
    symbol = _extract_symbol_from_assumption(assumption)
    if not symbol:
        return AssumptionResult(
            assumption=assumption,
            verdict="uncertain",
            confidence=0.0,
            details="Could not extract symbol/file name.",
        )

    # Find test files
    test_files = [
        f
        for f in rel_files
        if "test" in f.lower()
        and (f.endswith(".py") or f.endswith(".ts") or f.endswith(".js"))
    ]

    refs_in_tests = _find_references_in_files(workspace_root, symbol, test_files)

    if refs_in_tests:
        return AssumptionResult(
            assumption=assumption,
            verdict="pass",
            evidence_files=refs_in_tests[:MAX_EVIDENCE_DISPLAY],
            # Confidence 0.75: string-based reference detection is not as reliable as AST analysis
            confidence=0.75,
            details=f"'{symbol}' referenced in {len(refs_in_tests)} test file(s).",
        )
    else:
        return AssumptionResult(
            assumption=assumption,
            verdict="fail",
            evidence_files=[],
            confidence=0.6,
            details=f"No test files reference '{symbol}'.",
        )
