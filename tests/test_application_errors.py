"""
Tests cho các class trong application/errors.py
"""

from application.errors import (
    ApplicationError,
    UseCaseValidationError,
    OrchestrationError,
    DependencyContractError,
)
from domain.errors import DomainError


def test_application_error_base():
    """Test khởi tạo và thuộc tính cơ bản của ApplicationError."""
    err = ApplicationError("base error msg", code="custom_app_code", details={"k": "v"})
    assert str(err) == "base error msg"
    assert err.message == "base error msg"
    assert err.code == "custom_app_code"
    assert err.details == {"k": "v"}
    assert err.cause is None

    # Test default code
    err_default = ApplicationError("msg")
    assert err_default.code == "application_error"
    assert err_default.details == {}


def test_application_error_to_dict():
    """Test serialize error sang dict."""
    cause_err = ValueError("original root cause")
    err = ApplicationError(
        "wrapper error",
        code="wrapped_code",
        details={"path": "/tmp"},
        cause=cause_err,
    )
    d = err.to_dict()
    assert d["type"] == "ApplicationError"
    assert d["code"] == "wrapped_code"
    assert d["message"] == "wrapper error"
    assert d["details"] == {"path": "/tmp"}
    assert d["cause_type"] == "ValueError"


def test_application_error_from_domain():
    """Test factory method from_domain tạo ra ApplicationError từ DomainError."""
    domain_err = DomainError("domain crash", details={"domain_id": 123})

    # Gọi from_domain trực tiếp từ ApplicationError base class
    app_err = ApplicationError.from_domain(
        domain_err, code="new_app_code", details={"extra": True}
    )

    assert app_err.message == "domain crash"
    assert app_err.code == "new_app_code"
    # Kiểm tra việc merge details
    assert app_err.details == {"domain_id": 123, "extra": True}
    assert app_err.cause is domain_err

    # Gọi from_domain với mặc định code
    app_err_default = ApplicationError.from_domain(domain_err)
    assert app_err_default.code == "application_domain_error"


def test_use_case_validation_error():
    """Test UseCaseValidationError khởi tạo đúng."""
    err = UseCaseValidationError("invalid input", details={"field": "username"})
    assert isinstance(err, ApplicationError)
    assert isinstance(err, ValueError)
    assert err.code == "use_case_validation_error"
    assert err.details == {"field": "username"}


def test_orchestration_error():
    """Test OrchestrationError khởi tạo đúng."""
    err = OrchestrationError("orchestration failed", details={"step": "load"})
    assert isinstance(err, ApplicationError)
    assert err.code == "orchestration_error"


def test_dependency_contract_error():
    """Test DependencyContractError khởi tạo đúng."""
    err = DependencyContractError("contract violated", details={"port": "git"})
    assert isinstance(err, ApplicationError)
    assert err.code == "dependency_contract_error"
