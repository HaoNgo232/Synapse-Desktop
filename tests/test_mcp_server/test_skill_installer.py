"""
Test module cho skill_installer.py.

Kiem tra logic cai dat Synapse Agent Skills vao cac IDE:
- Tao dung cau truc folder <skill-name>/SKILL.md
- Format YAML frontmatter chinh xac
- Xu ly loi khi target khong hop le
- Check installed dung/sai
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_server.skill_installer import (
    SKILL_TARGETS,
    SKILL_TEMPLATES,
    _build_skill_md,
    _resolve_skills_dir,
    check_skills_installed,
    install_skills_for_target,
)

# ---------- Danh sach 5 skill keys can test ----------
EXPECTED_SKILLS = ["rp_build", "rp_review", "rp_refactor", "rp_investigate", "rp_test"]


class TestBuildSkillMd:
    """Kiem tra ham _build_skill_md() tao noi dung SKILL.md dung format."""

    def test_frontmatter_contains_name(self) -> None:
        """SKILL.md phai co truong name trong YAML frontmatter."""
        content = _build_skill_md("rp_build")
        assert content.startswith("---\n")
        assert "name: rp_build" in content

    def test_frontmatter_contains_description(self) -> None:
        """SKILL.md phai co truong description trong YAML frontmatter."""
        content = _build_skill_md("rp_review")
        assert "description: >-" in content

    def test_body_present_after_frontmatter(self) -> None:
        """Noi dung body markdown phai nam sau YAML frontmatter."""
        content = _build_skill_md("rp_build")
        # Frontmatter ket thuc bang "---\n\n"
        parts = content.split("---")
        # parts[0] la empty, parts[1] la frontmatter, phan sau la body
        assert len(parts) >= 3
        body = parts[2]
        assert "# Context Builder" in body

    @pytest.mark.parametrize("skill_key", EXPECTED_SKILLS)
    def test_all_skills_have_valid_content(self, skill_key: str) -> None:
        """Tat ca 5 skills deu tao duoc noi dung hop le."""
        content = _build_skill_md(skill_key)
        assert "---" in content
        assert f"name: {skill_key}" in content
        assert "description:" in content
        # Body khong rong
        assert len(content) > 100


class TestResolveSkillsDir:
    """Kiem tra ham _resolve_skills_dir() tra ve dung duong dan."""

    def test_global_target_expands_home(self) -> None:
        """Target global phai expand ~ thanh home dir."""
        result = _resolve_skills_dir("Claude Code")
        home = Path.home()
        assert result == home / ".claude" / "skills"

    def test_cursor_target(self) -> None:
        """Cursor skills luu tai ~/.cursor/skills."""
        result = _resolve_skills_dir("Cursor")
        assert result == Path.home() / ".cursor" / "skills"

    def test_antigravity_target(self) -> None:
        """Antigravity skills luu tai ~/.agents/skills."""
        result = _resolve_skills_dir("Antigravity")
        assert result == Path.home() / ".agents" / "skills"

    def test_kiro_target(self) -> None:
        """Kiro CLI skills luu tai ~/.kiro/skills."""
        result = _resolve_skills_dir("Kiro CLI")
        assert result == Path.home() / ".kiro" / "skills"

    def test_vscode_target_with_workspace(self) -> None:
        """VS Code/Copilot can workspace_path de tao duong dan project-level."""
        result = _resolve_skills_dir("VS Code (Copilot)", "/home/user/project")
        assert result == Path("/home/user/project/.github/skills")

    def test_vscode_target_without_workspace_raises(self) -> None:
        """VS Code/Copilot phai raise ValueError khi khong co workspace_path."""
        with pytest.raises(ValueError, match="workspace_path"):
            _resolve_skills_dir("VS Code (Copilot)")

    def test_unknown_target_raises(self) -> None:
        """Target khong ton tai phai raise ValueError."""
        with pytest.raises(ValueError, match="khong duoc ho tro"):
            _resolve_skills_dir("Unknown IDE")


class TestInstallSkillsForTarget:
    """Kiem tra ham install_skills_for_target() tao dung cau truc folder."""

    def test_creates_all_5_skill_folders(self, tmp_path: Path) -> None:
        """Phai tao du 5 folder voi file SKILL.md ben trong."""
        with patch.dict(
            "mcp_server.skill_installer.SKILL_TARGETS",
            {"TestIDE": {"skills_dir": str(tmp_path), "is_global": True}},
        ):
            ok, msg = install_skills_for_target("TestIDE")

        assert ok is True
        assert "5" in msg

        for skill_key in EXPECTED_SKILLS:
            skill_file = tmp_path / skill_key / "SKILL.md"
            assert skill_file.is_file(), f"Thieu file {skill_file}"

    def test_skill_md_content_has_frontmatter(self, tmp_path: Path) -> None:
        """File SKILL.md phai co YAML frontmatter dung format."""
        with patch.dict(
            "mcp_server.skill_installer.SKILL_TARGETS",
            {"TestIDE": {"skills_dir": str(tmp_path), "is_global": True}},
        ):
            install_skills_for_target("TestIDE")

        content = (tmp_path / "rp_build" / "SKILL.md").read_text(encoding="utf-8")
        assert content.startswith("---\n")
        assert "name: rp_build" in content
        assert "description: >-" in content

    def test_overwrite_existing_skills(self, tmp_path: Path) -> None:
        """Ghi de file SKILL.md neu da ton tai truoc do."""
        # Tao file cu voi noi dung khac
        old_dir = tmp_path / "rp_build"
        old_dir.mkdir(parents=True)
        (old_dir / "SKILL.md").write_text("old content")

        with patch.dict(
            "mcp_server.skill_installer.SKILL_TARGETS",
            {"TestIDE": {"skills_dir": str(tmp_path), "is_global": True}},
        ):
            ok, _ = install_skills_for_target("TestIDE")

        assert ok is True
        new_content = (tmp_path / "rp_build" / "SKILL.md").read_text(encoding="utf-8")
        assert new_content != "old content"
        assert "name: rp_build" in new_content

    def test_unknown_target_returns_error(self) -> None:
        """Target khong hop le phai tra ve (False, error message)."""
        ok, msg = install_skills_for_target("Unknown IDE")
        assert ok is False
        assert "khong duoc ho tro" in msg

    def test_vscode_needs_workspace_path(self) -> None:
        """VS Code (Copilot) phai tra ve loi khi thieu workspace_path."""
        ok, msg = install_skills_for_target("VS Code (Copilot)")
        assert ok is False
        assert "workspace_path" in msg

    def test_vscode_with_workspace_path(self, tmp_path: Path) -> None:
        """VS Code (Copilot) phai cai dat dung khi co workspace_path."""
        workspace = tmp_path / "my_project"
        workspace.mkdir()

        ok, msg = install_skills_for_target("VS Code (Copilot)", str(workspace))
        assert ok is True

        for skill_key in EXPECTED_SKILLS:
            skill_file = workspace / ".github" / "skills" / skill_key / "SKILL.md"
            assert skill_file.is_file()

    def test_permission_error_handling(self, tmp_path: Path) -> None:
        """Kiem tra xu ly loi khi khong co quyen ghi."""
        # Tao folder read-only
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        os.chmod(readonly_dir, 0o444)

        with patch.dict(
            "mcp_server.skill_installer.SKILL_TARGETS",
            {"TestIDE": {"skills_dir": str(readonly_dir), "is_global": True}},
        ):
            ok, msg = install_skills_for_target("TestIDE")

        assert ok is False
        assert "Loi" in msg

        # Cleanup: restore permissions
        os.chmod(readonly_dir, 0o755)


class TestCheckSkillsInstalled:
    """Kiem tra ham check_skills_installed() detect dung trang thai."""

    def test_returns_true_when_all_installed(self, tmp_path: Path) -> None:
        """Tra ve True khi tat ca 5 skills deu co file SKILL.md."""
        with patch.dict(
            "mcp_server.skill_installer.SKILL_TARGETS",
            {"TestIDE": {"skills_dir": str(tmp_path), "is_global": True}},
        ):
            # Cai dat truoc
            install_skills_for_target("TestIDE")
            result = check_skills_installed("TestIDE")

        assert result is True

    def test_returns_false_when_missing_one(self, tmp_path: Path) -> None:
        """Tra ve False khi thieu 1 skill bat ky."""
        with patch.dict(
            "mcp_server.skill_installer.SKILL_TARGETS",
            {"TestIDE": {"skills_dir": str(tmp_path), "is_global": True}},
        ):
            install_skills_for_target("TestIDE")
            # Xoa 1 file
            (tmp_path / "rp_build" / "SKILL.md").unlink()
            result = check_skills_installed("TestIDE")

        assert result is False

    def test_returns_false_for_unknown_target(self) -> None:
        """Tra ve False cho target khong ton tai."""
        assert check_skills_installed("Unknown IDE") is False

    def test_returns_false_when_empty_dir(self, tmp_path: Path) -> None:
        """Tra ve False khi thu muc skills rong."""
        with patch.dict(
            "mcp_server.skill_installer.SKILL_TARGETS",
            {"TestIDE": {"skills_dir": str(tmp_path), "is_global": True}},
        ):
            result = check_skills_installed("TestIDE")

        assert result is False


class TestSkillTargetsConfig:
    """Kiem tra cau hinh SKILL_TARGETS va SKILL_TEMPLATES dung."""

    def test_all_expected_targets_present(self) -> None:
        """Phai co du 5 IDE targets."""
        expected = {
            "Claude Code",
            "Cursor",
            "Antigravity",
            "Kiro CLI",
            "VS Code (Copilot)",
        }
        assert set(SKILL_TARGETS.keys()) == expected

    def test_all_expected_skills_present(self) -> None:
        """Phai co du 5 skill templates."""
        assert set(SKILL_TEMPLATES.keys()) == set(EXPECTED_SKILLS)

    @pytest.mark.parametrize("skill_key", EXPECTED_SKILLS)
    def test_template_has_required_fields(self, skill_key: str) -> None:
        """Moi template phai co name, description, body."""
        template = SKILL_TEMPLATES[skill_key]
        assert "name" in template
        assert "description" in template
        assert "body" in template
        assert template["name"] == skill_key
        assert len(template["description"]) > 20
        assert len(template["body"]) > 50
