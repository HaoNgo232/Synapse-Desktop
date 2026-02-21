"""
SelectionManager - Quan ly selection state cho file tree.

Tach rieng selection logic ra khoi FileTreeModel de:
1. Giam coupling giua Qt model va selection logic thuan tuy
2. Cho phep unit test selection ma khong can Qt
3. Tach biet concerns: FileTreeModel lo tree structure, SelectionManager lo selection

SelectionManager GIU NGUYEN moi selection logic cua FileTreeModel:
- _selected_paths: source of truth
- _selection_generation: stale data protection
- _last_resolved_files + _resolved_for_generation: cache resolved file list

API mirroring FileTreeModel's selection methods.

Thread Safety: All methods MUST be called from the main (UI) thread only.
PySide6 enforces this for UI components. No internal locking needed.
"""

from typing import Iterator, Optional, Set, Callable


class SelectionManager:
    """
    Quan ly selection state thuanly, khong phu thuoc Qt.

    Thread Safety: All methods MUST be called from the main (UI) thread only.
    Callback on_selection_changed duoc goi SAU moi lan selection doi
    de FileTreeModel co the emit signal va repaint.
    """

    def __init__(
        self,
        on_selection_changed: Optional[Callable[[Set[str], int], None]] = None,
    ) -> None:
        """
        Khoi tao SelectionManager.

        Args:
            on_selection_changed: Callback(selected_paths, generation) goi khi selection doi.
        """
        self._selected_paths: Set[str] = set()

        # Stale data protection
        self._selection_generation: int = 0
        self._last_resolved_files: Set[str] = set()
        self._resolved_for_generation: int = -1

        self._on_selection_changed = on_selection_changed

    @property
    def selected_paths(self) -> Set[str]:
        """Tra ve ban sao cua selected paths."""
        return set(self._selected_paths)

    @property
    def selection_generation(self) -> int:
        """Tra ve generation counter hien tai."""
        return self._selection_generation

    @property
    def resolved_for_generation(self) -> int:
        """Tra ve generation ma resolved files duoc compute."""
        return self._resolved_for_generation

    @property
    def last_resolved_files(self) -> Set[str]:
        """Tra ve ban sao cua resolved files."""
        return set(self._last_resolved_files)

    def is_selected(self, path: str) -> bool:
        """Kiem tra path co dang selected hay khong."""
        return path in self._selected_paths

    def count(self) -> int:
        """Tra ve so luong paths dang selected."""
        return len(self._selected_paths)

    # === Internal access methods (zero-copy, chi dung cho internal read-only) ===

    def iterate_paths(self) -> Iterator[str]:
        """Tra ve iterator qua selected paths KHONG tao copy.

        CHI SU DUNG cho internal read-only access (vd: get_selected_paths).
        KHONG modify set trong khi dang iterate.
        """
        return iter(self._selected_paths)

    def is_resolved(self, path: str) -> bool:
        """Kiem tra path co trong resolved files hay khong (O(1), khong copy)."""
        return path in self._last_resolved_files

    def iterate_resolved(self) -> Iterator[str]:
        """Tra ve iterator qua resolved files KHONG tao copy.

        CHI SU DUNG cho internal read-only access.
        """
        return iter(self._last_resolved_files)

    def resolved_count(self) -> int:
        """Tra ve so luong resolved files (khong copy)."""
        return len(self._last_resolved_files)

    def add(self, path: str) -> None:
        """Them 1 path vao selection (khong trigger callback)."""
        self._selected_paths.add(path)

    def remove(self, path: str) -> None:
        """Xoa 1 path khoi selection (khong trigger callback)."""
        self._selected_paths.discard(path)

    def add_many(self, paths: Set[str]) -> int:
        """
        Them nhieu paths vao selection.

        Args:
            paths: Set paths can them

        Returns:
            So paths moi duoc them (chua co truoc do)
        """
        before = len(self._selected_paths)
        self._selected_paths.update(paths)
        return len(self._selected_paths) - before

    def remove_many(self, paths: Set[str]) -> int:
        """
        Xoa nhieu paths khoi selection.

        Args:
            paths: Set paths can xoa

        Returns:
            So paths da bi xoa
        """
        before = len(self._selected_paths)
        self._selected_paths -= paths
        return before - len(self._selected_paths)

    def replace_all(self, paths: Set[str]) -> None:
        """
        Thay the toan bo selection bang set moi.

        Tu dong bump generation de dam bao stale detection hoat dong.
        Callers KHONG can goi bump_generation() rieng sau replace_all().

        Dung cho session restore va batch selection update.
        """
        self._selected_paths = set(paths)
        self.bump_generation()

    def clear(self) -> None:
        """Xoa toan bo selection."""
        self._selected_paths.clear()

    def set_resolved_files(self, files: Set[str], generation: int) -> None:
        """
        Luu resolved file list va generation tuong ung.

        Goi boi token counting pipeline sau khi resolve xong.
        """
        self._last_resolved_files = set(files)
        self._resolved_for_generation = generation

    def get_resolved_files_if_fresh(self) -> Optional[Set[str]]:
        """
        Tra ve resolved files NEU con fresh (cung generation).

        Returns:
            Set resolved files neu fresh, None neu stale
        """
        if self._resolved_for_generation == self._selection_generation:
            return set(self._last_resolved_files)
        return None

    def bump_generation(self) -> int:
        """
        Tang generation counter va invalidate resolved files.

        PHAI goi sau MOI thay doi selection de stale data protection hoat dong.

        Returns:
            Generation moi sau khi tang
        """
        self._last_resolved_files.clear()
        self._resolved_for_generation = -1
        self._selection_generation += 1
        return self._selection_generation

    def notify_changed(self) -> None:
        """
        Thong bao selection da thay doi qua callback.

        Goi method nay SAU KHI da hoan thanh tat ca mutations
        va bump_generation().
        """
        if self._on_selection_changed is not None:
            self._on_selection_changed(
                set(self._selected_paths), self._selection_generation
            )

    def reset(self) -> None:
        """
        Reset toan bo state. Dung khi doi workspace.

        Generation duoc BUMP (khong reset ve 0) de dam bao monotonic invariant.
        Bat ky worker nao dang giu generation cu se luon bi stale.

        Khong trigger callback.
        """
        self._selected_paths.clear()
        self._last_resolved_files.clear()
        self._resolved_for_generation = -1
        # KHONG reset ve 0 — phai tang de dam bao monotonic increasing
        self._selection_generation += 1
