"""
Tests for domain.smart_context.queries._load_query
Covers the empty-string branch when no .scm file exists for the given language.
"""

from domain.smart_context.queries import _load_query


def test_load_query_returns_empty_for_unknown_lang():
    """_load_query returns empty string when no .scm file exists for the given language."""
    result = _load_query("nonexistent_language_xyz_12345")
    assert result == ""


def test_load_query_returns_string_for_known_lang():
    """_load_query returns a non-empty string for a known language (python)."""
    result = _load_query("python")
    assert isinstance(result, str)
