#!/usr/bin/env python3
"""
Script tu dong cap nhat tat ca handlers de ho tro auto-detection.

Thay doi:
- workspace_path: str -> workspace_path: Optional[str] = None
- Them ctx: Context = None
- Chuyen sang async
- Thay inline validation bang await WorkspaceManager.resolve(workspace_path, ctx)
"""

import re
from pathlib import Path

HANDLERS_DIR = Path("mcp_server/handlers")

# Danh sach handlers can cap nhat (tru token_handler da xong)
HANDLERS = [
    "analysis_handler.py",
    "context_handler.py",
    "dependency_handler.py",
    "file_handler.py",
    "git_handler.py",
    "selection_handler.py",
    "structure_handler.py",
    "workspace_handler.py",
    "workflow_handler.py",
]


def add_imports(content: str) -> str:
    """Them imports can thiet neu chua co."""
    if "from mcp.server.fastmcp import Context" in content:
        return content

    # Tim dong import cuoi cung
    lines = content.split("\n")
    last_import_idx = 0
    for i, line in enumerate(lines):
        if line.startswith(("import ", "from ")):
            last_import_idx = i

    # Chen imports moi sau dong import cuoi
    lines.insert(last_import_idx + 1, "")
    lines.insert(last_import_idx + 2, "from mcp.server.fastmcp import Context")
    if (
        "from infrastructure.mcp.core.workspace_manager import WorkspaceManager"
        not in content
    ):
        lines.insert(
            last_import_idx + 3,
            "from infrastructure.mcp.core.workspace_manager import WorkspaceManager",
        )

    return "\n".join(lines)


def update_tool_signature(content: str) -> str:
    """Cap nhat signature cua moi tool function."""

    # Pattern: @mcp_instance.tool() ... def tool_name(workspace_path: str, ...)
    pattern = r"(@mcp_instance\.tool\(\).*?)\n(\s+)def\s+(\w+)\s*\((.*?workspace_path:\s*str.*?)\)(\s*->.*?):"

    def replace_fn(match):
        decorator = match.group(1)
        indent = match.group(2)
        func_name = match.group(3)
        params = match.group(4)
        return_type = match.group(5)

        # Thay workspace_path: str -> workspace_path: Optional[str] = None
        params = re.sub(
            r"workspace_path:\s*str", "workspace_path: Optional[str] = None", params
        )

        # Them ctx: Context = None neu chua co
        if "ctx:" not in params:
            params = params.rstrip() + ",\n" + indent + "    ctx: Context = None,"

        # Them async
        return f"{decorator}\n{indent}async def {func_name}({params}){return_type}:"

    content = re.sub(pattern, replace_fn, content, flags=re.DOTALL)

    return content


def update_workspace_resolution(content: str) -> str:
    """Thay inline validation bang await WorkspaceManager.resolve()."""

    # Pattern 1: ws = Path(workspace_path).resolve() + validation
    pattern1 = r"ws = Path\(workspace_path\)\.resolve\(\)\s+if not ws\.(exists|is_dir)\(\):.*?return.*?Error.*?\n.*?if not ws\.(is_dir|exists)\(\):.*?return.*?Error.*?\n"

    replacement1 = """try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        """

    content = re.sub(pattern1, replacement1, content, flags=re.DOTALL)

    # Pattern 2: Inline validation don gian
    pattern2 = r'ws = Path\(workspace_path\)\.resolve\(\)\s+if not ws\.is_dir\(\):\s+return f"Error:.*?"\s+'

    replacement2 = """try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        """

    content = re.sub(pattern2, replacement2, content, flags=re.DOTALL)

    return content


def process_handler(handler_path: Path) -> None:
    """Xu ly mot handler file."""
    print(f"Processing {handler_path.name}...")

    content = handler_path.read_text(encoding="utf-8")

    # Buoc 1: Them imports
    content = add_imports(content)

    # Buoc 2: Cap nhat signatures
    content = update_tool_signature(content)

    # Buoc 3: Cap nhat workspace resolution
    content = update_workspace_resolution(content)

    # Ghi lai file
    handler_path.write_text(content, encoding="utf-8")
    print(f"  ✓ Updated {handler_path.name}")


def main():
    """Main entry point."""
    print("Updating MCP handlers for auto-detection support...\n")

    for handler_name in HANDLERS:
        handler_path = HANDLERS_DIR / handler_name
        if not handler_path.exists():
            print(f"  ⚠ Skipping {handler_name} (not found)")
            continue

        try:
            process_handler(handler_path)
        except Exception as e:
            print(f"  ✗ Error processing {handler_name}: {e}")

    print("\n✓ All handlers updated successfully!")


if __name__ == "__main__":
    main()
