#!/usr/bin/env python3
"""Auto-update remaining handlers with async and auto-detection."""

import re
from pathlib import Path


def update_handler(file_path: Path):
    """Update a single handler file."""
    content = file_path.read_text(encoding="utf-8")

    # Skip if already updated
    if "from mcp.server.fastmcp import Context" in content:
        print(f"  ⏭️  {file_path.name} already updated")
        return False

    # 1. Add imports after existing imports
    lines = content.split("\n")
    last_import_idx = 0
    for i, line in enumerate(lines):
        if line.startswith(("import ", "from ")) and "mcp_server" not in line:
            last_import_idx = i

    lines.insert(last_import_idx + 1, "")
    lines.insert(last_import_idx + 2, "from mcp.server.fastmcp import Context")
    lines.insert(
        last_import_idx + 3,
        "from infrastructure.mcp.core.workspace_manager import WorkspaceManager",
    )

    content = "\n".join(lines)

    # 2. Update tool signatures - find @mcp_instance.tool() blocks
    # Pattern: @mcp_instance.tool() followed by def tool_name(workspace_path: str, ...)
    pattern = r"(@mcp_instance\.tool\(\)[^\n]*\n\s+)def\s+(\w+)\s*\(\s*workspace_path:\s*str\s*,([^)]*)\)\s*->\s*str:"

    def replace_signature(match):
        decorator_and_indent = match.group(1)
        func_name = match.group(2)
        other_params = match.group(3).strip()

        # Build new signature
        if other_params:
            new_sig = f"{decorator_and_indent}async def {func_name}(\n        {other_params},\n        workspace_path: Optional[str] = None,\n        ctx: Context = None,\n    ) -> str:"
        else:
            new_sig = f"{decorator_and_indent}async def {func_name}(\n        workspace_path: Optional[str] = None,\n        ctx: Context = None,\n    ) -> str:"

        return new_sig

    content = re.sub(pattern, replace_signature, content, flags=re.MULTILINE)

    # 3. Replace workspace validation
    # Pattern 1: ws = Path(workspace_path).resolve() + validation
    pattern1 = r'ws = Path\(workspace_path\)\.resolve\(\)\s+if not ws\.is_dir\(\):\s+return f"Error:.*?"\s+'
    replacement1 = """try:
            ws = await WorkspaceManager.resolve(workspace_path, ctx)
        except ValueError as e:
            return f"Error: {e}"

        """

    content = re.sub(pattern1, replacement1, content, flags=re.DOTALL)

    # Pattern 2: More complex validation
    pattern2 = r"ws = Path\(workspace_path\)\.resolve\(\)\s+if not ws\.exists\(\):.*?return.*?\n.*?if not ws\.is_dir\(\):.*?return.*?\n"
    content = re.sub(pattern2, replacement1, content, flags=re.DOTALL)

    file_path.write_text(content, encoding="utf-8")
    print(f"  ✅ {file_path.name} updated")
    return True


def main():
    handlers_dir = Path("mcp_server/handlers")

    # Handlers to update
    handlers = [
        "context_handler.py",
        "dependency_handler.py",
        "workflow_handler.py",
    ]

    print("Updating remaining handlers...\n")

    updated = 0
    for handler_name in handlers:
        handler_path = handlers_dir / handler_name
        if not handler_path.exists():
            print(f"  ⚠️  {handler_name} not found")
            continue

        try:
            if update_handler(handler_path):
                updated += 1
        except Exception as e:
            print(f"  ❌ Error updating {handler_name}: {e}")

    print(f"\n✅ Updated {updated}/{len(handlers)} handlers")


if __name__ == "__main__":
    main()
