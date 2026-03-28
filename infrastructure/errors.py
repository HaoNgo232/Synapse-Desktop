"""
Infrastructure Error Model - He thong loi chuan cho adapter/external systems.

Adapter layer map loi ky thuat (network, filesystem, parser, persistence)
vao cac loai loi co nghia de application layer xu ly nhat quan.
"""

from typing import Any, Dict, Optional


class InfrastructureError(Exception):
    """Base error cho infrastructure layer."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "infrastructure_error",
        details: Optional[Dict[str, Any]] = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.retryable = retryable

    def to_dict(self) -> Dict[str, Any]:
        """Serialize error de phuc vu mapping/logging."""
        return {
            "type": self.__class__.__name__,
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "retryable": self.retryable,
        }


class PersistenceError(InfrastructureError):
    """Loi thao tac persistence/storage."""

    def __init__(
        self, message: str, *, details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(
            message,
            code="persistence_error",
            details=details,
            retryable=False,
        )


class NetworkError(InfrastructureError):
    """Loi ket noi network/API."""

    def __init__(
        self, message: str, *, details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(
            message,
            code="network_error",
            details=details,
            retryable=True,
        )


class ExternalServiceError(InfrastructureError):
    """Loi tu external provider/service."""

    def __init__(
        self,
        message: str,
        *,
        details: Optional[Dict[str, Any]] = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(
            message,
            code="external_service_error",
            details=details,
            retryable=retryable,
        )


class ParserError(InfrastructureError):
    """Loi parser/AST/query engine."""

    def __init__(
        self, message: str, *, details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(
            message,
            code="parser_error",
            details=details,
            retryable=False,
        )


class FileSystemError(InfrastructureError):
    """Loi filesystem/I-O."""

    def __init__(
        self,
        message: str,
        *,
        details: Optional[Dict[str, Any]] = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(
            message,
            code="filesystem_error",
            details=details,
            retryable=retryable,
        )


class InfrastructureTimeoutError(InfrastructureError, TimeoutError):
    """Loi timeout khi goi external system."""

    def __init__(
        self,
        message: str,
        *,
        details: Optional[Dict[str, Any]] = None,
        retryable: bool = True,
    ) -> None:
        super().__init__(
            message,
            code="infrastructure_timeout_error",
            details=details,
            retryable=retryable,
        )


class ConfigurationError(InfrastructureError, ValueError):
    """Loi cau hinh adapter/provider."""

    def __init__(
        self, message: str, *, details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(
            message,
            code="configuration_error",
            details=details,
            retryable=False,
        )
