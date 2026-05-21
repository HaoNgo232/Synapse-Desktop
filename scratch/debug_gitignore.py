import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from infrastructure.filesystem.ignore_engine import IgnoreEngine

with tempfile.TemporaryDirectory() as tmpdir:
    repo = Path(tmpdir) / "repo"
    repo.mkdir()

    (repo / ".gitignore").write_text("/build\n")
    (repo / ".git").mkdir()

    subdir = repo / "subdir"
    subdir.mkdir()

    sub_build = subdir / "build"
    sub_build.mkdir()
    (sub_build / "file2.txt").write_text("subdir build file")

    (subdir / "normal.txt").write_text("normal file")

    engine = IgnoreEngine()

    # Simulate scan_directory spec_stack setup
    spec_stack = []
    git_root = engine.find_git_root(subdir)
    print("git_root:", git_root)
    print("subdir:", subdir)

    # Parent spec
    parent_spec = engine.build_pathspec(
        git_root, use_default_ignores=False, use_gitignore=True
    )
    spec_stack.append((parent_spec, git_root))
    print("Parent patterns:", parent_spec.patterns)

    # Subspec
    spec = engine.build_pathspec(subdir, use_default_ignores=True, use_gitignore=True)
    spec_stack.append((spec, subdir))
    print("Subspec patterns:", spec.patterns)

    # Now check subdir/build
    entry = sub_build
    print("\nChecking entry:", entry)

    for s, base in reversed(spec_stack):
        rel_to_base = entry.relative_to(base)
        rel_to_base_str = str(rel_to_base)
        if entry.is_dir() and not rel_to_base_str.endswith("/"):
            rel_to_base_str += "/"

        res = s.check_file(rel_to_base_str)
        print(f"Base: {base}, RelPath: {rel_to_base_str}")
        if res is not None:
            print(f"  Matched! include={res.include}")
        else:
            print("  Not matched")
