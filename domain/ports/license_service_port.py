from abc import ABC, abstractmethod
from domain.licensing.entities import LicenseInfo

class ILicenseService(ABC):
    @abstractmethod
    def verify_license_key(self, key_str: str) -> LicenseInfo:
        """Decode, parse, and verify a cryptographic license key string."""
        pass
