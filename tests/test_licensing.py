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
        error_message="",
    )
    assert info.license_id == "LIC-12345"
    assert info.email == "test@example.com"
    assert info.expiry_date == "2027-12-31"
    assert info.product == "Synapse Desktop"
    assert info.is_valid is True
    assert info.error_message == ""


def test_license_service_registry_not_registered():
    # Reset state to prevent test pollution
    original_service = DomainRegistry._license_service
    DomainRegistry._license_service = None
    try:
        with pytest.raises(AttributeError):
            DomainRegistry.license_service()
    finally:
        DomainRegistry._license_service = original_service


def test_license_service_empty_or_malformed_key():
    from infrastructure.adapters.license_service import Ed25519LicenseService

    service = Ed25519LicenseService()
    info = service.verify_license_key("")
    assert info.is_valid is False
    assert "empty" in info.error_message.lower()

    info2 = service.verify_license_key("SYNAPSE-KEY.invalidpayload.invalidsig")
    assert info2.is_valid is False
    assert (
        "structure" in info2.error_message.lower()
        or "decoding" in info2.error_message.lower()
        or "decode" in info2.error_message.lower()
    )


def test_app_settings_contains_license_key():
    from domain.config.app_settings import AppSettings

    settings = AppSettings()
    assert hasattr(settings, "license_key")
    assert settings.license_key == ""

    settings_dict = settings.to_dict()
    assert "license_key" in settings_dict

    loaded_settings = AppSettings.from_dict({"license_key": "SYNAPSE-KEY.abc.123"})
    assert loaded_settings.license_key == "SYNAPSE-KEY.abc.123"


def test_cryptographic_verification_with_generated_keys():
    import json
    import base64
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization
    from infrastructure.adapters.license_service import Ed25519LicenseService

    # Generate temporary key pair
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    service = Ed25519LicenseService(public_key_pem=public_pem)

    # Sign custom payload
    payload = {
        "license_id": "LIC-TEST-1",
        "email": "tester@test.com",
        "expiry_date": "2030-01-01",
        "product": "Synapse Desktop",
    }
    payload_str = json.dumps(payload, separators=(",", ":"))
    payload_b64 = (
        base64.urlsafe_b64encode(payload_str.encode("utf-8"))
        .decode("utf-8")
        .rstrip("=")
    )

    signature = private_key.sign(payload_b64.encode("utf-8"))
    sig_b64 = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")

    full_key = f"SYNAPSE-KEY.{payload_b64}.{sig_b64}"

    # Verify the signature
    info = service.verify_license_key(full_key)
    assert info.is_valid is True
    assert info.license_id == "LIC-TEST-1"
    assert info.email == "tester@test.com"


def test_embedded_key_pair_verification():
    from infrastructure.adapters.license_service import Ed25519LicenseService

    service = Ed25519LicenseService()

    # Generate live using tool parameters inside test
    from tools.license_generator import sign_license

    live_key = sign_license("LIC-LIVE", "live@test.com", 30)
    info = service.verify_license_key(live_key)
    assert info.is_valid is True
    assert info.email == "live@test.com"


def test_lifetime_license_verification():
    from infrastructure.adapters.license_service import Ed25519LicenseService
    from tools.license_generator import sign_license

    service = Ed25519LicenseService()

    # Generate and verify lifetime key
    lifetime_key = sign_license(
        "LIC-LIFETIME-TEST", "lifetime@test.com", 365, lifetime=True
    )
    info = service.verify_license_key(lifetime_key)

    assert info.is_valid is True
    assert info.expiry_date == "never"
    assert info.email == "lifetime@test.com"
    assert info.license_id == "LIC-LIFETIME-TEST"
