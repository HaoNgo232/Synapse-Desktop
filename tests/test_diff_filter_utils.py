"""Tests for diff filter utilities."""

from shared.utils.diff_filter_utils import should_auto_exclude


def test_auto_exclude_lock_files() -> None:
    assert should_auto_exclude("pnpm-lock.yaml") is True
    assert should_auto_exclude("package-lock.json") is True
    assert should_auto_exclude("some/path/yarn.lock") is True
    assert should_auto_exclude("Cargo.lock") is True


def test_auto_exclude_glob_patterns() -> None:
    assert should_auto_exclude("styles.min.css") is True
    assert should_auto_exclude("bundle.min.js") is True
    assert should_auto_exclude("source.map") is True


def test_no_exclude_normal_files() -> None:
    assert should_auto_exclude("src/app.py") is False
    assert should_auto_exclude("README.md") is False
    assert should_auto_exclude("src/lock_manager.py") is False
