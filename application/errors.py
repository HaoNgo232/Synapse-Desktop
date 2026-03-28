"""
Application Error Model - He thong loi chuan cho use case/orchestration layer.

Layer nay map loi tu domain/infrastructure thanh semantics phu hop voi use case,
tranh de adapter layer phai hieu chi tiet noi bo.
"""

from typing import Any, Dict, Optional

from domain.errors import DomainError


class ApplicationError(Exception):
    """Base error cho application layer."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "application_error",
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.cause = cause

    @classmethod
    def from_domain(
        cls,
        err: DomainError,
        *,
        code: str = "application_domain_error",
        details: Optional[Dict[str, Any]] = None,
    ) -> "ApplicationError":
        """Factory helper de wrap DomainError nhat quan."""
        merged_details = dict(err.details)
        if details:
            merged_details.update(details)
        # Cac subclass co the khong nhan tham so `code`; fallback ve base class
        # de tranh TypeError khi goi factory qua subclass.
        target_cls = ApplicationError if cls is not ApplicationError else cls
        return target_cls(
            err.message,
            code=code,
            details=merged_details,
            cause=err,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize error de phuc vu adapter mapping."""
        return {
            "type": self.__class__.__name__,
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "cause_type": self.cause.__class__.__name__ if self.cause else None,
        }


class UseCaseValidationError(ApplicationError, ValueError):
    """Loi validate command/input o use case boundary."""

    def __init__(
        self,
        message: str,
        *,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code="use_case_validation_error",
            details=details,
            cause=cause,
        )


class OrchestrationError(ApplicationError):
    """Loi dieu phoi flow use case."""

    def __init__(
        self,
        message: str,
        *,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code="orchestration_error",
            details=details,
            cause=cause,
        )


class DependencyContractError(ApplicationError):
    """Loi vi pham contract voi dependency/port."""

    def __init__(
        self,
        message: str,
        *,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code="dependency_contract_error",
            details=details,
            cause=cause,
        )


class WorkflowExecutionError(ApplicationError):
    """Loi thuc thi workflow use case."""

    def __init__(
        self,
        message: str,
        *,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> None:
        super().__init__(
            message,
            code="workflow_execution_error",
            details=details,
            cause=cause,
        )
