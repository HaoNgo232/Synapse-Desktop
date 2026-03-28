"""
Domain Error Model - He thong loi chuan cho domain layer.

Muc tieu:
- Chuan hoa semantics loi o domain.
- Khong phu thuoc vao infrastructure/application details.
- Ho tro mapping nhat quan qua cac layer.
"""

from typing import Any, Dict, Optional


class DomainError(Exception):
    """Base error cho tat ca loi nghiep vu thuoc domain."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "domain_error",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize error de phuc vu logging/telemetry."""
        return {
            "type": self.__class__.__name__,
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


class DomainValidationError(DomainError, ValueError):
    """Loi validate input/command o domain boundary."""

    def __init__(
        self,
        message: str,
        *,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            code="domain_validation_error",
            details=details,
        )


class InvariantViolationError(DomainError):
    """Loi vi pham invariant cua domain model."""

    def __init__(
        self,
        message: str,
        *,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            code="domain_invariant_violation",
            details=details,
        )


class BusinessRuleViolationError(DomainError):
    """Loi vi pham business rule/policy."""

    def __init__(
        self,
        message: str,
        *,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            code="domain_business_rule_violation",
            details=details,
        )
