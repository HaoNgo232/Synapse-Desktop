"""
Test suite để verify các bugs được report trong code review.

Kiểm tra:
- BUG #1: Top-level import có thể gây fail toàn bộ handler registration
- BUG #2: Silent data loss do norm_to_orig dict collision
- BUG #3: _normalize resolve sai khi workspace_root là None
- BUG #4: TOCTOU race condition trong session file creation
"""

import json
import pytest
import threading
import time
from pathlib import Path

from domain.prompt.generator import generate_file_contents_xml


class TestBug1TopLevelImportFailure:
    """Test BUG #1 - Top-level import có thể gây fail toàn bộ handler registration."""

    def test_context_handler_imports_at_top_level(self):
        """Verify rằng DependencyResolver và PromptBuildService được import ở top-level."""
        # Read context_handler.py
        handler_file = Path("infrastructure/mcp/handlers/context_handler.py")
        if not handler_file.exists():
            pytest.skip("context_handler.py not found")

        content = handler_file.read_text()

        # Check if imports are at top-level (not inside functions)
        lines = content.split("\n")
        import_lines = []
        in_function = False

        for i, line in enumerate(lines, 1):
            if line.strip().startswith("def ") or line.strip().startswith("async def "):
                in_function = True
            if in_function and (
                line.startswith("def ")
                or line.startswith("async def ")
                or line.startswith("class ")
            ):
                in_function = False

            if (
                "from application.services.dependency_resolver import" in line
                or "from application.services.prompt_build_service import" in line
            ):
                import_lines.append((i, line, in_function))

        # Report findings
        top_level_imports = [imp for imp in import_lines if not imp[2]]

        if top_level_imports:
            print("\n⚠️  BUG #1 CONFIRMED: Top-level imports detected:")
            for line_num, line, _ in top_level_imports:
                print(f"  Line {line_num}: {line.strip()}")
            print(
                "\n  Risk: If tree-sitter fails to load, entire handler registration fails"
            )
            print("  Recommendation: Use lazy imports inside functions that need them")
        else:
            print("\n✅ BUG #1 NOT PRESENT: All imports are lazy (inside functions)")


class TestBug2DictCollision:
    """Test BUG #2 - Silent data loss do norm_to_orig dict collision."""

    def test_duplicate_normalized_paths_cause_collision(self, tmp_path):
        """Test rằng hai paths khác nhau nhưng normalize về cùng file gây data loss."""
        # Arrange: Create a test file
        test_file = tmp_path / "src" / "main.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("print('hello')")

        # Two different path formats pointing to same file
        relative_path = "src/main.py"
        absolute_path = str(test_file.resolve())

        selected_paths = {relative_path, absolute_path}
        codemap_paths = {relative_path}  # Only one in codemap

        # Act
        result = generate_file_contents_xml(
            selected_paths=selected_paths,
            workspace_root=tmp_path,
            use_relative_paths=False,
            codemap_paths=codemap_paths,
        )

        # Assert: Check if both paths are processed
        # If collision occurs, one path will be silently dropped
        occurrences = result.count("main.py")

        if occurrences < 2:
            print("\n⚠️  BUG #2 CONFIRMED: Dict collision detected!")
            print(f"  Expected 2 occurrences of 'main.py', got {occurrences}")
            print(f"  Selected paths: {selected_paths}")
            print("  One path was silently dropped due to dict key collision")
        else:
            print(
                f"\n✅ BUG #2 NOT PRESENT: Both paths processed correctly ({occurrences} occurrences)"
            )

    def test_collision_with_absolute_and_relative_mix(self, tmp_path):
        """Test collision khi mix absolute và relative paths."""
        # Arrange
        file1 = tmp_path / "test.py"
        file1.write_text("def foo(): pass")

        # Same file, different representations
        paths = {
            "test.py",
            str(file1),
            str(file1.resolve()),
        }

        codemap_paths = {"test.py"}

        # Act
        result = generate_file_contents_xml(
            selected_paths=paths,
            workspace_root=tmp_path,
            codemap_paths=codemap_paths,
        )

        # Count unique file entries
        file_count = result.count("<file path=")

        print(f"\n  Input: {len(paths)} path variations")
        print(f"  Output: {file_count} file entries")

        if file_count < len(paths):
            print(f"  ⚠️  Collision detected: {len(paths) - file_count} paths lost")


class TestBug3NormalizeWithNoneWorkspace:
    """Test BUG #3 - _normalize resolve sai khi workspace_root là None."""

    def test_normalize_relative_path_without_workspace_root(self, tmp_path):
        """Test _normalize với relative path khi workspace_root=None."""
        # Arrange
        test_file = tmp_path / "test.py"
        test_file.write_text("print('test')")

        # Use relative path
        selected_paths = {"test.py"}
        codemap_paths = {"test.py"}

        # Act: Call with workspace_root=None
        try:
            result = generate_file_contents_xml(
                selected_paths=selected_paths,
                workspace_root=None,  # BUG: This causes wrong resolution
                codemap_paths=codemap_paths,
            )

            # If no error, check if path was resolved correctly
            if "test.py" in result:
                print(
                    "\n⚠️  BUG #3 CONFIRMED: Relative path processed without workspace_root"
                )
                print("  Path was resolved using os.getcwd() instead of workspace root")
                print(
                    "  This can cause incorrect file resolution in MCP server context"
                )
            else:
                print("\n✅ Path not found in output (expected behavior)")

        except (ValueError, FileNotFoundError) as e:
            print(f"\n✅ BUG #3 NOT PRESENT: Proper error raised: {e}")

    def test_normalize_behavior_with_cwd_mismatch(self, tmp_path, monkeypatch):
        """Test khi CWD khác workspace directory."""
        # Arrange: Create workspace
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        test_file = workspace / "src" / "main.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("def main(): pass")

        # Change CWD to different directory
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        monkeypatch.chdir(other_dir)

        # Act: Use relative path with workspace_root=None
        selected_paths = {"src/main.py"}

        try:
            result = generate_file_contents_xml(
                selected_paths=selected_paths,
                workspace_root=None,
                codemap_paths=set(),
            )

            # Check if file was found (it shouldn't be, since CWD != workspace)
            if "main.py" not in result or "Error" in result:
                print("\n⚠️  BUG #3 CONFIRMED: File not found due to CWD mismatch")
                print(f"  CWD: {other_dir}")
                print(f"  Workspace: {workspace}")
                print("  Relative path resolved incorrectly")

        except Exception as e:
            print(f"\n  Exception raised: {e}")


class TestBug4RaceCondition:
    """Test BUG #4 - TOCTOU race condition trong session file creation."""

    def test_concurrent_session_file_creation(self, tmp_path):
        """Test race condition khi nhiều threads tạo session file đồng thời."""
        from infrastructure.mcp.handlers.selection_handler import _locked_read_modify_write

        # Arrange
        session_file = tmp_path / ".synapse" / "selection.json"
        results = []
        errors = []

        def add_file(file_path: str):
            """Helper function to add file to selection."""
            try:

                def modifier(current: list[str]) -> list[str]:
                    return current + [file_path]

                result = _locked_read_modify_write(session_file, modifier)
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Act: Spawn multiple threads trying to create file simultaneously
        threads = []
        for i in range(10):
            t = threading.Thread(target=add_file, args=(f"file_{i}.py",))
            threads.append(t)

        # Start all threads at once
        for t in threads:
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # Assert: Check for data loss or errors
        if errors:
            print(
                f"\n⚠️  BUG #4 CONFIRMED: {len(errors)} errors during concurrent access:"
            )
            for e in errors[:3]:  # Show first 3 errors
                print(f"  - {e}")

        # Check final state
        if session_file.exists():
            final_data = json.loads(session_file.read_text())
            final_count = len(final_data.get("selected_files", []))

            print(f"\n  Threads: {len(threads)}")
            print(f"  Final file count: {final_count}")

            if final_count < len(threads):
                print(
                    f"  ⚠️  Data loss detected: {len(threads) - final_count} files missing"
                )
                print("  Race condition in file creation caused overwrites")
            else:
                print("  ✅ All files preserved")
        else:
            print("\n  ⚠️  Session file not created")

    def test_race_between_exists_check_and_write(self, tmp_path):
        """Test TOCTOU race giữa exists() check và write_text()."""

        session_file = tmp_path / ".synapse" / "selection.json"

        # Simulate race: Thread 1 checks exists(), Thread 2 creates file, Thread 1 overwrites
        race_detected = False

        def create_with_delay():
            """Create file with artificial delay to trigger race."""
            if not session_file.exists():
                time.sleep(0.01)  # Delay to allow race window
                session_file.parent.mkdir(parents=True, exist_ok=True)
                session_file.write_text(
                    json.dumps({"selected_files": ["important.py"]})
                )

        def overwrite_empty():
            """Try to create empty file (simulating the bug)."""
            if not session_file.exists():
                time.sleep(0.005)
                session_file.parent.mkdir(parents=True, exist_ok=True)
                session_file.write_text(json.dumps({"selected_files": []}))

        # Start both operations
        t1 = threading.Thread(target=create_with_delay)
        t2 = threading.Thread(target=overwrite_empty)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Check result
        if session_file.exists():
            data = json.loads(session_file.read_text())
            files = data.get("selected_files", [])

            if len(files) == 0:
                print("\n⚠️  BUG #4 CONFIRMED: Race condition caused data loss")
                print("  File with 'important.py' was overwritten with empty selection")
                race_detected = True
            else:
                print(f"\n✅ No race detected, files preserved: {files}")

        return race_detected


def run_all_bug_verifications():
    """Run all bug verification tests and generate report."""
    print("\n" + "=" * 80)
    print("BUG VERIFICATION REPORT - Code Review Findings")
    print("=" * 80)

    # Create temp directory for tests
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        print("\n[1/4] Testing BUG #1 - Top-level Import Failure")
        print("-" * 80)
        test1 = TestBug1TopLevelImportFailure()
        test1.test_context_handler_imports_at_top_level()

        print("\n[2/4] Testing BUG #2 - Dict Collision Data Loss")
        print("-" * 80)
        test2 = TestBug2DictCollision()
        test2.test_duplicate_normalized_paths_cause_collision(tmp_path)
        test2.test_collision_with_absolute_and_relative_mix(tmp_path)

        print("\n[3/4] Testing BUG #3 - Normalize with None Workspace")
        print("-" * 80)
        test3 = TestBug3NormalizeWithNoneWorkspace()
        test3.test_normalize_relative_path_without_workspace_root(tmp_path)

        print("\n[4/4] Testing BUG #4 - TOCTOU Race Condition")
        print("-" * 80)
        test4 = TestBug4RaceCondition()
        test4.test_concurrent_session_file_creation(tmp_path)

        print("\n" + "=" * 80)
        print("VERIFICATION COMPLETE")
        print("=" * 80)


if __name__ == "__main__":
    run_all_bug_verifications()
