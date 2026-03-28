"""
MCP Error Mapper - Chuan hoa map exception -> thong diep phan hoi cho MCP tools.

Muc tieu:
- Khong de adapter layer expose raw traceback ra ben ngoai.
- Thong nhat format loi cho AI clients.
- Giu lai ngu nghia retryable/validation/dependency.
"""

from dataclasses import dataclass, field
from typing import Any, Dict

from application.errors import ApplicationError, UseCaseValidationError
from domain.errors import DomainError, DomainValidationError
from infrastructure.errors import InfrastructureError


def _empty_error_details() -> Dict[str, Any]:
    """Tao dict rong co typing ro rang cho dataclass factory."""
    return {}


@dataclass(frozen=True)
class MCPErrorPayload:
    """Thong tin loi da duoc map o muc adapter boundary."""

    category: str
    code: str
    message: str
    retryable: bool = False
    details: Dict[str, Any] = field(default_factory=_empty_error_details)


def map_exception_to_payload(exc: BaseException) -> MCPErrorPayload:
    """Map exception bat ky ve payload chuan cho MCP response."""
    if isinstance(exc, UseCaseValidationError):
        return MCPErrorPayload(
            category="application",
            code=exc.code,
            message=exc.message,
            retryable=False,
            details=exc.details,
        )

    if isinstance(exc, ApplicationError):
        return MCPErrorPayload(
            category="application",
            code=exc.code,
            message=exc.message,
            retryable=False,
            details=exc.details,
        )

    if isinstance(exc, DomainValidationError):
        return MCPErrorPayload(
            category="domain",
            code=exc.code,
            message=exc.message,
            retryable=False,
            details=exc.details,
        )

    if isinstance(exc, DomainError):
        return MCPErrorPayload(
            category="domain",
            code=exc.code,
            message=exc.message,
            retryable=False,
            details=exc.details,
        )

    if isinstance(exc, InfrastructureError):
        return MCPErrorPayload(
            category="infrastructure",
            code=exc.code,
            message=exc.message,
            retryable=exc.retryable,
            details=exc.details,
        )

    if isinstance(exc, ValueError):
        return MCPErrorPayload(
            category="validation",
            code="value_error",
            message=str(exc),
            retryable=False,
        )

    return MCPErrorPayload(
        category="unexpected",
        code="unexpected_error",
        message=str(exc) if str(exc) else "Unexpected internal error",
        retryable=False,
    )


def format_mcp_error(exc: BaseException, *, prefix: str = "Error") -> str:
    """Format payload thanh text output de tra ve tu MCP tool."""
    payload = map_exception_to_payload(exc)
    base = f"{prefix}: [{payload.category}:{payload.code}] {payload.message}"
    if payload.retryable:
        base += " (retryable)"
    return base
