import pytest
from domain.licensing.entities import LicenseInfo
from domain.ports.registry import DomainRegistry

def test_license_info_entity():
    info = LicenseInfo(
        license_id="LIC-12345",
        email="test@example.com",
        expiry_date="2027-12-31",
        product="Synapse Desktop",
        is_valid=True,
        error_message=""
    )
    assert info.license_id == "LIC-12345"
    assert info.email == "test@example.com"
    assert info.expiry_date == "2027-12-31"
    assert info.product == "Synapse Desktop"
    assert info.is_valid is True
    assert info.error_message == ""

def test_license_service_registry_not_registered():
    with pytest.raises(AttributeError):
        # Should raise error before registration port is added to DomainRegistry
        DomainRegistry.license_service()

def test_license_service_empty_or_malformed_key():
    from infrastructure.adapters.license_service import Ed25519LicenseService
    service = Ed25519LicenseService()
    info = service.verify_license_key("")
    assert info.is_valid is False
    assert "empty" in info.error_message.lower()

    info2 = service.verify_license_key("SYNAPSE-KEY.invalidpayload.invalidsig")
    assert info2.is_valid is False
    assert "structure" in info2.error_message.lower() or "decoding" in info2.error_message.lower() or "decode" in info2.error_message.lower()


