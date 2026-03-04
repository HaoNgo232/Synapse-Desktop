"""
Tests cho mcp_server/core/constants.py

Kiem tra cac regex patterns va constants duoc dinh nghia dung:
- SAFE_GIT_REF: validate git ref names, chan injection
- INLINE_COMMENT_RE: match inline comments
- STRING_LITERAL_RE: match string literals
- GIT_TIMEOUT: co gia tri hop ly
"""

from mcp_server.core.constants import (
    GIT_TIMEOUT,
    INLINE_COMMENT_RE,
    SAFE_GIT_REF,
    STRING_LITERAL_RE,
    logger,
)


class TestSafeGitRef:
    """Kiem tra SAFE_GIT_REF chan dung cac git ref injection."""

    def test_valid_branch_names(self):
        """Cac branch name hop le phai match."""
        valid_refs = [
            "main",
            "develop",
            "feature/login",
            "release/v1.0",
            "HEAD",
            "HEAD~1",
            "HEAD^2",
            "v1.0.0",
            "abc123def",
            "origin/main",
        ]
        for ref in valid_refs:
            assert SAFE_GIT_REF.match(ref), f"'{ref}' nen duoc chap nhan"

    def test_blocks_dash_prefix(self):
        """Ref bat dau bang '-' bi chan (chong git option injection)."""
        dangerous_refs = [
            "--output=/tmp/pwned",
            "-n",
            "--exec=rm -rf /",
            "-v",
        ]
        for ref in dangerous_refs:
            assert not SAFE_GIT_REF.match(ref), f"'{ref}' phai bi chan"

    def test_blocks_empty_string(self):
        """Chuoi rong khong match."""
        assert not SAFE_GIT_REF.match("")

    def test_blocks_special_characters(self):
        """Cac ky tu dac biet ngoai whitelist bi chan."""
        dangerous = [
            "ref; rm -rf /",
            "ref && malicious",
            "ref | cat /etc/passwd",
            "ref$(command)",
            "ref`injection`",
        ]
        for ref in dangerous:
            assert not SAFE_GIT_REF.match(ref), f"'{ref}' phai bi chan"


class TestInlineCommentRegex:
    """Kiem tra INLINE_COMMENT_RE match inline comments dung."""

    def test_python_comment(self):
        """Match Python-style comment (#)."""
        line = "x = 1  # this is a comment"
        match = INLINE_COMMENT_RE.search(line)
        assert match is not None
        assert match.group().startswith("#")

    def test_js_comment(self):
        """Match JS/C-style comment (//)."""
        line = "let x = 1;  // this is a comment"
        match = INLINE_COMMENT_RE.search(line)
        assert match is not None
        assert match.group().startswith("//")

    def test_no_comment(self):
        """Dong khong co comment -> khong match."""
        line = "x = 1 + 2"
        match = INLINE_COMMENT_RE.search(line)
        assert match is None


class TestStringLiteralRegex:
    """Kiem tra STRING_LITERAL_RE match string literals dung."""

    def test_double_quoted_string(self):
        """Match string trong dau nhay doi."""
        line = 'x = "hello world"'
        matches = STRING_LITERAL_RE.findall(line)
        assert '"hello world"' in matches

    def test_single_quoted_string(self):
        """Match string trong dau nhay don."""
        line = "x = 'hello world'"
        matches = STRING_LITERAL_RE.findall(line)
        assert "'hello world'" in matches

    def test_escaped_quotes(self):
        """Match string chua escaped quotes."""
        line = r'x = "say \"hello\""'
        matches = STRING_LITERAL_RE.findall(line)
        assert len(matches) >= 1

    def test_no_strings(self):
        """Dong khong co string -> khong match."""
        line = "x = 42 + y"
        matches = STRING_LITERAL_RE.findall(line)
        assert len(matches) == 0


class TestGitTimeout:
    """Kiem tra GIT_TIMEOUT co gia tri hop ly."""

    def test_timeout_is_positive(self):
        """Timeout phai la so duong."""
        assert GIT_TIMEOUT > 0

    def test_timeout_reasonable_range(self):
        """Timeout trong khoang hop ly (5-60 seconds)."""
        assert 5 <= GIT_TIMEOUT <= 60


class TestLogger:
    """Kiem tra logger duoc cau hinh dung."""

    def test_logger_name(self):
        """Logger co ten chinh xac."""
        assert logger.name == "synapse.mcp"
