"""
Constants module - Tap trung cac hang so dung chung trong MCP Server.

Chua regex patterns, timeouts, va logger instance duoc
su dung boi nhieu handlers khac nhau.
"""

import logging
import re

# Logger chung cho toan bo MCP server
logger = logging.getLogger("synapse.mcp")

# Regex validate git ref name: chi cho phep ky tu an toan (branch, tag, commit hash).
# Khong cho phep bat dau bang '-' de chan git option injection (vi du: '--output=/tmp/pwned').
SAFE_GIT_REF = re.compile(r"^[A-Za-z0-9_./@^~][A-Za-z0-9_./@^~\-]*$")

# Timeout cho moi lenh git subprocess (seconds). 15s la du cho local git operations.
GIT_TIMEOUT = 15

# Regex cho find_references: loc string literals va inline comments truoc khi match symbol
INLINE_COMMENT_RE = re.compile(r"(#|//).*$")
STRING_LITERAL_RE: re.Pattern[str] = re.compile(
    r'"(?:[^"\\]|\\.)*"|' + r"'(?:[^'\\]|\\.)*'"
)
