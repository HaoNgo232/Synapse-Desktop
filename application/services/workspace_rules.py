"""
Workspace Rules - Quan ly project rule files per workspace.

Luu danh sach rule files vao .synapse/project_rules.json trong workspace.
Rule files se tu dong duoc include vao prompt khi copy context.
"""

import json
import logging
from pathlib import Path
from typing import Set

logger = logging.getLogger(__name__)

RULES_FILE = "project_rules.json"


def _get_rules_path(workspace: Path) -> Path:
    """Get path to project_rules.json in workspace."""
    try:
        synapse_dir = workspace / ".synapse"
        synapse_dir.mkdir(parents=True, exist_ok=True)
        return synapse_dir / RULES_FILE
    except (OSError, PermissionError) as e:
        logger.warning("Cannot create .synapse directory: %s", e)
        # Return path anyway, caller will handle errors
        return workspace / ".synapse" / RULES_FILE


def load_workspace_rules(workspace: Path) -> Set[str]:
    """
    Load rule files from workspace.

    Returns:
        Set of relative paths (e.g., {"AGENTS.md", ".cursorrules"})
    """
    rules_path = _get_rules_path(workspace)
    if not rules_path.exists():
        return set()

    try:
        data = json.loads(rules_path.read_text(encoding="utf-8"))
        return set(data.get("rule_files", []))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load workspace rules: %s", e)
        return set()


def save_workspace_rules(workspace: Path, rules: Set[str]) -> None:
    """Save rule files to workspace."""
    rules_path = _get_rules_path(workspace)
    try:
        data = {"rule_files": sorted(rules)}
        rules_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as e:
        logger.error("Failed to save workspace rules: %s", e)


def add_rule_file(workspace: Path, file_path: str) -> None:
    """
    Mark a file as project rule.

    Args:
        workspace: Workspace root
        file_path: Absolute path to file
    """
    try:
        rel_path = Path(file_path).relative_to(workspace).as_posix()
    except ValueError:
        logger.warning("File not in workspace: %s", file_path)
        return

    rules = load_workspace_rules(workspace)
    rules.add(rel_path)
    save_workspace_rules(workspace, rules)
    logger.info("Added rule file: %s", rel_path)


def remove_rule_file(workspace: Path, file_path: str) -> None:
    """
    Unmark a file as project rule.

    Args:
        workspace: Workspace root
        file_path: Absolute path to file
    """
    try:
        rel_path = Path(file_path).relative_to(workspace).as_posix()
    except ValueError:
        return

    rules = load_workspace_rules(workspace)
    rules.discard(rel_path)
    save_workspace_rules(workspace, rules)
    logger.info("Removed rule file: %s", rel_path)


def is_rule_file(workspace: Path, file_path: str) -> bool:
    """
    Check if a file is marked as project rule.

    Args:
        workspace: Workspace root
        file_path: Absolute path to file

    Returns:
        True if file is a rule file
    """
    try:
        rel_path = Path(file_path).relative_to(workspace).as_posix()
    except ValueError:
        return False

    rules = load_workspace_rules(workspace)
    return rel_path in rules


def get_rule_file_contents(workspace: Path) -> str:
    """
    Load and format all rule files from workspace.

    Returns:
        Formatted string with all rule file contents
    """
    rules = load_workspace_rules(workspace)
    if not rules:
        return ""

    contents = []
    for rel_path in sorted(rules):
        file_path = workspace / rel_path
        if not file_path.exists():
            logger.warning("Rule file not found: %s", rel_path)
            continue

        try:
            if file_path.stat().st_size > 10 * 1024 * 1024:  # 10MB limit
                logger.warning("Rule file too large, skipping: %s", rel_path)
                continue

            content = file_path.read_text(encoding="utf-8", errors="replace")
            contents.append(f"--- Rule File: {rel_path} ---\n{content}\n")
        except (OSError, PermissionError) as e:
            logger.warning("Cannot read rule file %s: %s", rel_path, e)

    return "\n".join(contents)
