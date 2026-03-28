"""
Architecture Governance Checker - Kiem tra luat kien truc theo layer.

Muc tieu:
- Enforce dependency direction o muc import.
- Phat hien service phinh to (god service) theo threshold.
- Phat hien cycle giua cac layer chinh.

Che do:
- report (mac dinh): in bao cao, exit 0.
- strict: fail neu co vi pham moi so voi baseline.

Su dung:
    python tools/architecture/check_architecture.py
    python tools/architecture/check_architecture.py --strict
    python tools/architecture/check_architecture.py --write-baseline
"""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = ROOT / "tools" / "architecture" / "baseline.json"

TARGET_LAYERS = ("domain", "application", "infrastructure", "presentation")

FORBIDDEN_IMPORTS: Dict[str, Set[str]] = {
    "domain": {"application", "infrastructure", "presentation"},
    "application": {"presentation"},
    "infrastructure": {"presentation"},
    "presentation": {"domain", "infrastructure"},
}

MAX_SERVICE_LINES = 450
MAX_SERVICE_PUBLIC_METHODS = 12


def _empty_violation_list() -> List[str]:
    """Tao list rong co typing ro rang cho dataclass factory."""
    return []


@dataclass
class Violations:
    """Tong hop cac loai vi pham kien truc."""

    import_violations: List[str] = field(default_factory=_empty_violation_list)
    god_service_violations: List[str] = field(default_factory=_empty_violation_list)
    layer_cycles: List[str] = field(default_factory=_empty_violation_list)

    def to_dict(self) -> Dict[str, List[str]]:
        return {
            "import_violations": sorted(set(self.import_violations)),
            "god_service_violations": sorted(set(self.god_service_violations)),
            "layer_cycles": sorted(set(self.layer_cycles)),
        }


def _iter_python_files() -> Iterable[Path]:
    """Duyet tat ca file python trong 4 layer chinh."""
    for layer in TARGET_LAYERS:
        layer_dir = ROOT / layer
        if not layer_dir.exists():
            continue
        for py_file in layer_dir.rglob("*.py"):
            if "/__pycache__/" in str(py_file).replace("\\", "/"):
                continue
            yield py_file


def _detect_layer(path: Path) -> str | None:
    """Xac dinh layer theo top-level folder."""
    rel = path.relative_to(ROOT)
    top = rel.parts[0]
    if top in TARGET_LAYERS:
        return top
    return None


def _extract_imported_roots(node: ast.AST) -> List[str]:
    """Lay root package tu import statement."""
    roots: List[str] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            roots.append(alias.name.split(".")[0])
    elif isinstance(node, ast.ImportFrom):
        if node.module:
            roots.append(node.module.split(".")[0])
    return roots


def _collect_import_violations() -> Tuple[List[str], Dict[str, Set[str]]]:
    """Thu thap vi pham import direction + layer graph edges."""
    violations: List[str] = []
    layer_edges: Dict[str, Set[str]] = {layer: set() for layer in TARGET_LAYERS}

    for py_file in _iter_python_files():
        layer = _detect_layer(py_file)
        if layer is None:
            continue

        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue

            imported_roots = _extract_imported_roots(node)
            for root in imported_roots:
                if root in TARGET_LAYERS and root != layer:
                    layer_edges[layer].add(root)

                if root in FORBIDDEN_IMPORTS.get(layer, set()):
                    rel = py_file.relative_to(ROOT).as_posix()
                    violations.append(f"{rel} imports forbidden root '{root}'")

    return violations, layer_edges


def _collect_god_service_violations() -> List[str]:
    """Phat hien file service qua lon hoac qua nhieu methods public."""
    violations: List[str] = []

    candidate_dirs = [
        ROOT / "application" / "services",
        ROOT / "application" / "use_cases",
    ]

    for candidate_dir in candidate_dirs:
        if not candidate_dir.exists():
            continue

        for py_file in candidate_dir.rglob("*.py"):
            rel = py_file.relative_to(ROOT).as_posix()
            try:
                content = py_file.read_text(encoding="utf-8")
                lines = content.splitlines()
            except Exception:
                continue

            if len(lines) > MAX_SERVICE_LINES:
                violations.append(
                    f"{rel} exceeds MAX_SERVICE_LINES={MAX_SERVICE_LINES} (actual={len(lines)})"
                )

            try:
                tree = ast.parse(content)
            except Exception:
                continue

            for node in tree.body:
                if not isinstance(node, ast.ClassDef):
                    continue
                if not (
                    node.name.endswith("Service")
                    or node.name.endswith("UseCase")
                    or node.name.endswith("Registry")
                ):
                    continue

                public_methods = [
                    n
                    for n in node.body
                    if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")
                ]
                if len(public_methods) > MAX_SERVICE_PUBLIC_METHODS:
                    violations.append(
                        f"{rel}:{node.name} exceeds MAX_SERVICE_PUBLIC_METHODS="
                        f"{MAX_SERVICE_PUBLIC_METHODS} (actual={len(public_methods)})"
                    )

    return violations


def _collect_layer_cycles(layer_edges: Dict[str, Set[str]]) -> List[str]:
    """Phat hien cycle giua cac layer bang DFS."""
    cycles: Set[str] = set()

    def dfs(node: str, path: List[str], visited_local: Set[str]) -> None:
        for nxt in layer_edges.get(node, set()):
            if nxt in path:
                cycle = path[path.index(nxt) :] + [nxt]
                cycles.add(" -> ".join(cycle))
                continue
            if nxt in visited_local:
                continue
            dfs(nxt, path + [nxt], visited_local | {nxt})

    for layer in TARGET_LAYERS:
        dfs(layer, [layer], {layer})

    return sorted(cycles)


def collect_violations() -> Violations:
    """Chay toan bo checks va tra ve violations."""
    import_violations, layer_edges = _collect_import_violations()
    god_services = _collect_god_service_violations()
    layer_cycles = _collect_layer_cycles(layer_edges)

    return Violations(
        import_violations=import_violations,
        god_service_violations=god_services,
        layer_cycles=layer_cycles,
    )


def _load_baseline() -> Dict[str, List[str]]:
    """Doc baseline file, fallback ve dict rong neu khong ton tai."""
    if not BASELINE_PATH.exists():
        return {
            "import_violations": [],
            "god_service_violations": [],
            "layer_cycles": [],
        }

    try:
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {
            "import_violations": [],
            "god_service_violations": [],
            "layer_cycles": [],
        }


def _compute_new_violations(
    current: Dict[str, List[str]],
    baseline: Dict[str, List[str]],
) -> Dict[str, List[str]]:
    """So sanh current violations voi baseline de tim vi pham moi."""
    result: Dict[str, List[str]] = {}
    for key in ("import_violations", "god_service_violations", "layer_cycles"):
        cur = set(current.get(key, []))
        base = set(baseline.get(key, []))
        result[key] = sorted(cur - base)
    return result


def _print_report(current: Dict[str, List[str]]) -> None:
    """In bao cao violation de developer doc nhanh."""
    print("Architecture Governance Report")
    print("=" * 40)

    for key, title in (
        ("import_violations", "Import Violations"),
        ("god_service_violations", "God Service Violations"),
        ("layer_cycles", "Layer Cycles"),
    ):
        items = current.get(key, [])
        print(f"\n{title}: {len(items)}")
        for item in items[:20]:
            print(f"  - {item}")
        if len(items) > 20:
            print(f"  ... and {len(items) - 20} more")


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Synapse architecture governance checker"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail if there are new violations compared to baseline",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Write current violations to baseline.json",
    )
    args = parser.parse_args()

    violations = collect_violations()
    current = violations.to_dict()

    if args.write_baseline:
        BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_PATH.write_text(
            json.dumps(current, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Baseline written to: {BASELINE_PATH}")
        return 0

    _print_report(current)

    if not args.strict:
        return 0

    baseline = _load_baseline()
    new_violations = _compute_new_violations(current, baseline)

    total_new = sum(len(v) for v in new_violations.values())
    if total_new == 0:
        print("\nStrict check passed: no new architecture violations.")
        return 0

    print("\nStrict check failed: detected new architecture violations.")
    for key, title in (
        ("import_violations", "New import violations"),
        ("god_service_violations", "New god service violations"),
        ("layer_cycles", "New layer cycles"),
    ):
        items = new_violations[key]
        if not items:
            continue
        print(f"\n{title}: {len(items)}")
        for item in items:
            print(f"  - {item}")

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
