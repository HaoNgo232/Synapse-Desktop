import base64
import json
import argparse
from datetime import datetime, timedelta
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

# Embedded Private Key PEM corresponding to the Public Key embedded in license_service.py
# In a real environment, this private key should NEVER be checked into source code.
# For this lab/offline showcase, we bundle it to make testing self-contained and reproducible.
PRIVATE_KEY_PEM = b"""-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIPz5pPscE5vU7d7vDq2xV/wD6Q3FqB5rG0T/4Wk7bX2D
-----END PRIVATE KEY-----"""


def generate_key_pair():
    """Helper function to generate a brand new keypair for future replacement."""
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    print("=== NEW PRIVATE KEY PEM (Keep Secret!) ===")
    print(private_pem.decode("utf-8"))
    print("=== NEW PUBLIC KEY PEM (Embed in App) ===")
    print(public_pem.decode("utf-8"))


def sign_license(
    license_id: str, email: str, days_valid: int, lifetime: bool = False
) -> str:
    # Read private key
    private_key = serialization.load_pem_private_key(PRIVATE_KEY_PEM, password=None)
    if not isinstance(private_key, ed25519.Ed25519PrivateKey):
        raise ValueError("Key is not an Ed25519 private key")

    # Use UTC to calculate expiry date safely
    if lifetime:
        expiry_date = "never"
    else:
        expiry_date = (datetime.utcnow() + timedelta(days=days_valid)).strftime(
            "%Y-%m-%d"
        )

    payload = {
        "license_id": license_id,
        "email": email,
        "expiry_date": expiry_date,
        "product": "Synapse Desktop",
    }

    # Dump compactly with no extra spaces to keep the payload clean
    payload_str = json.dumps(payload, separators=(",", ":"))
    payload_bytes = payload_str.encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")

    # Sign the raw base64 payload bytes (just like verified in license_service.py)
    signature = private_key.sign(payload_b64.encode("utf-8"))
    signature_b64 = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")

    license_key = f"SYNAPSE-KEY.{payload_b64}.{signature_b64}"
    return license_key


def main():
    parser = argparse.ArgumentParser(description="Synapse Desktop License Generator")
    parser.add_argument("--id", default="LIC-10001", help="License unique identifier")
    parser.add_argument(
        "--email", default="developer@synapse.com", help="Licensed email owner"
    )
    parser.add_argument("--days", type=int, default=365, help="Number of days valid")
    parser.add_argument(
        "--lifetime",
        action="store_true",
        help="Generate a lifetime license with no expiration",
    )
    parser.add_argument(
        "--keygen",
        action="store_true",
        help="Generate a new keypair instead of signing",
    )

    args = parser.parse_args()

    if args.keygen:
        generate_key_pair()
    else:
        key = sign_license(args.id, args.email, args.days, args.lifetime)
        print("=== GENERATED LICENSE KEY ===")
        print(key)
        print("=============================")


if __name__ == "__main__":
    main()
