"""
ICacheable Protocol - Interface cho tat ca caches trong ung dung.

Dinh nghia contract chung de CacheRegistry co the invalidate tat ca caches
mot cach thong nhat qua mot API duy nhat.

Protocol pattern cho phep cac cache implementations khong can ke thua,
chi can implement dung methods.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class ICacheable(Protocol):
    """
    Protocol cho cac cache co the duoc quan ly boi CacheRegistry.

    Bat ky class nao implement 3 methods nay deu co the duoc register.
    """

    def invalidate_path(self, path: str) -> None:
        """
        Xoa cache entries lien quan den mot file path cu the.

        Goi khi FileWatcher phat hien file thay doi hoac bi xoa.

        Args:
            path: Duong dan tuyet doi cua file da thay doi
        """
        ...

    def invalidate_all(self) -> None:
        """
        Xoa toan bo cache.

        Goi khi workspace thay doi hoac user reset.
        """
        ...

    def size(self) -> int:
        """
        Tra ve so luong entries hien co trong cache.

        Dung cho monitoring va debugging.

        Returns:
            So entries trong cache
        """
        ...
