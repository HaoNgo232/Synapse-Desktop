import logging
import requests
from datetime import datetime, timezone
from domain.licensing.entities import LicenseInfo
from domain.ports.license_service_port import ILicenseService

logger = logging.getLogger(__name__)


class GumroadLicenseService(ILicenseService):
    DEFAULT_PRODUCT_ID = "g3j8iqBm8C6LIwSAqro1Ww=="
    API_URL = "https://api.gumroad.com/v2/licenses/verify"

    def __init__(self, product_id: str = DEFAULT_PRODUCT_ID) -> None:
        self._product_id = product_id

    def verify_license_key(self, key_str: str) -> LicenseInfo:
        if not key_str or not key_str.strip():
            return LicenseInfo(
                "", "", "", "", is_valid=False, error_message="License key is empty"
            )

        key_str = key_str.strip()

        try:
            payload = {
                "product_id": self._product_id,
                "license_key": key_str,
                "increment_uses_count": True,
            }
            response = requests.post(self.API_URL, json=payload, timeout=10)

            if response.status_code == 404:
                return LicenseInfo(
                    license_id=key_str,
                    email="",
                    expiry_date="",
                    product="",
                    is_valid=False,
                    error_message="Invalid license key",
                )

            if response.status_code != 200:
                try:
                    err_msg = response.json().get(
                        "message", f"HTTP error {response.status_code}"
                    )
                except Exception:
                    logger.error(
                        "LicenseService: validation request failed", exc_info=True
                    )
                    err_msg = f"HTTP error {response.status_code}"
                return LicenseInfo(
                    license_id=key_str,
                    email="",
                    expiry_date="",
                    product="",
                    is_valid=False,
                    error_message=err_msg,
                )

            data = response.json()
            success = data.get("success", False)
            if not success:
                err_msg = data.get("message", "Verification failed")
                return LicenseInfo(
                    license_id=key_str,
                    email="",
                    expiry_date="",
                    product="",
                    is_valid=False,
                    error_message=err_msg,
                )

            uses = data.get("uses", 0)
            purchase = data.get("purchase", {})
            email = purchase.get("email", "")
            product_name = purchase.get("product_name", "")
            purchase_date = purchase.get("sale_timestamp", "")
            refunded = purchase.get("refunded", False)
            disputed = purchase.get("disputed", False)

            if refunded:
                return LicenseInfo(
                    license_id=key_str,
                    email=email,
                    expiry_date="never",
                    product=product_name,
                    is_valid=False,
                    error_message="License key has been refunded",
                    uses=uses,
                    purchase_date=purchase_date,
                    refunded=refunded,
                    disputed=disputed,
                )

            if disputed:
                return LicenseInfo(
                    license_id=key_str,
                    email=email,
                    expiry_date="never",
                    product=product_name,
                    is_valid=False,
                    error_message="License key is disputed",
                    uses=uses,
                    purchase_date=purchase_date,
                    refunded=refunded,
                    disputed=disputed,
                )

            subscription_ended_at = purchase.get("subscription_ended_at")
            if subscription_ended_at:
                try:
                    dt_str = subscription_ended_at.replace("Z", "+00:00")
                    end_dt = datetime.fromisoformat(dt_str)
                    if datetime.now(timezone.utc) > end_dt:
                        return LicenseInfo(
                            license_id=key_str,
                            email=email,
                            expiry_date=subscription_ended_at[:10],
                            product=product_name,
                            is_valid=False,
                            error_message="Subscription has expired",
                            uses=uses,
                            purchase_date=purchase_date,
                            refunded=refunded,
                            disputed=disputed,
                        )
                except Exception as e:
                    logger.warning("Failed to parse subscription_ended_at: %s", e)

            return LicenseInfo(
                license_id=key_str,
                email=email,
                expiry_date="never",
                product=product_name,
                is_valid=True,
                uses=uses,
                purchase_date=purchase_date,
                refunded=refunded,
                disputed=disputed,
            )

        except requests.exceptions.RequestException as e:
            logger.error("Gumroad API connection error: %s", e)
            return LicenseInfo(
                license_id=key_str,
                email="",
                expiry_date="",
                product="",
                is_valid=False,
                error_message=f"Network error: {e}",
            )
