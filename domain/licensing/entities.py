from dataclasses import dataclass

@dataclass
class LicenseInfo:
    license_id: str
    email: str
    expiry_date: str  # YYYY-MM-DD
    product: str
    is_valid: bool = False
    error_message: str = ""
