"""
Tests cho SelectionManager.

Verify:
1. add/remove/clear/replace_all operations
2. Selection generation tracking va stale detection
3. Resolved files management
4. Callback notification
5. Thread-safe reads
"""

from services.selection_manager import SelectionManager


class TestSelectionBasic:
    """Test basic selection operations."""

    def test_empty_initial(self):
        """Selection khoi tao rong."""
        mgr = SelectionManager()
        assert mgr.count() == 0
        assert mgr.selected_paths == set()

    def test_add_single(self):
        """Them 1 path vao selection."""
        mgr = SelectionManager()
        mgr.add("/a.py")
        assert mgr.is_selected("/a.py")
        assert mgr.count() == 1

    def test_remove_single(self):
        """Xoa 1 path khoi selection."""
        mgr = SelectionManager()
        mgr.add("/a.py")
        mgr.remove("/a.py")
        assert not mgr.is_selected("/a.py")
        assert mgr.count() == 0

    def test_remove_nonexistent(self):
        """Xoa path khong ton tai khong loi."""
        mgr = SelectionManager()
        mgr.remove("/nonexistent")
        assert mgr.count() == 0

    def test_add_many(self):
        """add_many tra ve so paths moi."""
        mgr = SelectionManager()
        mgr.add("/a.py")
        added = mgr.add_many({"/a.py", "/b.py", "/c.py"})
        assert added == 2
        assert mgr.count() == 3

    def test_remove_many(self):
        """remove_many tra ve so paths da xoa."""
        mgr = SelectionManager()
        mgr.add_many({"/a.py", "/b.py", "/c.py"})
        removed = mgr.remove_many({"/b.py", "/c.py", "/d.py"})
        assert removed == 2
        assert mgr.count() == 1

    def test_replace_all(self):
        """replace_all thay the toan bo selection."""
        mgr = SelectionManager()
        mgr.add_many({"/a.py", "/b.py"})
        mgr.replace_all({"/x.py", "/y.py"})
        assert mgr.count() == 2
        assert mgr.is_selected("/x.py")
        assert not mgr.is_selected("/a.py")

    def test_replace_all_bumps_generation(self):
        """replace_all tu dong bump generation de tranh stale data."""
        mgr = SelectionManager()
        mgr.add("/a.py")
        gen_before = mgr.selection_generation
        # Set resolved files truoc replace_all
        mgr.set_resolved_files({"/a.py"}, gen_before)
        assert mgr.get_resolved_files_if_fresh() is not None

        # replace_all phai bump generation → resolved files tro thanh stale
        mgr.replace_all({"/x.py"})
        assert mgr.selection_generation > gen_before
        assert mgr.get_resolved_files_if_fresh() is None

    def test_clear(self):
        """clear xoa toan bo selection."""
        mgr = SelectionManager()
        mgr.add_many({"/a.py", "/b.py"})
        mgr.clear()
        assert mgr.count() == 0


class TestSelectionGeneration:
    """Test generation tracking va stale data protection."""

    def test_initial_generation_zero(self):
        """Generation bat dau tu 0."""
        mgr = SelectionManager()
        assert mgr.selection_generation == 0

    def test_bump_generation(self):
        """bump_generation tang counter."""
        mgr = SelectionManager()
        gen = mgr.bump_generation()
        assert gen == 1
        assert mgr.selection_generation == 1

    def test_bump_clears_resolved(self):
        """bump_generation clears resolved files."""
        mgr = SelectionManager()
        mgr.set_resolved_files({"/a.py"}, 0)
        mgr.bump_generation()
        assert mgr.get_resolved_files_if_fresh() is None

    def test_resolved_files_fresh(self):
        """get_resolved_files_if_fresh tra ve set khi cung generation."""
        mgr = SelectionManager()
        mgr.set_resolved_files({"/a.py", "/b.py"}, mgr.selection_generation)
        result = mgr.get_resolved_files_if_fresh()
        assert result == {"/a.py", "/b.py"}

    def test_resolved_files_stale(self):
        """get_resolved_files_if_fresh tra ve None khi generation khac."""
        mgr = SelectionManager()
        mgr.set_resolved_files({"/a.py"}, mgr.selection_generation)
        mgr.bump_generation()  # Makes it stale
        result = mgr.get_resolved_files_if_fresh()
        assert result is None


class TestSelectionReset:
    """Test reset method."""

    def test_reset_clears_all(self):
        """reset xoa toan bo state, generation duoc BUMP (monotonic)."""
        mgr = SelectionManager()
        mgr.add_many({"/a.py", "/b.py"})
        mgr.bump_generation()
        gen_before = mgr.selection_generation
        mgr.set_resolved_files({"/a.py"}, mgr.selection_generation)

        mgr.reset()

        assert mgr.count() == 0
        # Generation phai tang (monotonic), KHONG reset ve 0
        assert mgr.selection_generation > gen_before
        assert mgr.get_resolved_files_if_fresh() is None


class TestSelectionCallback:
    """Test on_selection_changed callback."""

    def test_callback_called(self):
        """notify_changed goi callback voi paths va generation."""
        received = []

        def callback(paths, gen):
            received.append((paths, gen))

        mgr = SelectionManager(on_selection_changed=callback)
        mgr.add("/a.py")
        mgr.bump_generation()
        mgr.notify_changed()

        assert len(received) == 1
        assert "/a.py" in received[0][0]
        assert received[0][1] == 1

    def test_no_callback_no_error(self):
        """notify_changed khong loi khi khong co callback."""
        mgr = SelectionManager()
        mgr.notify_changed()  # No error


class TestSelectedPathsCopy:
    """Test selected_paths tra ve ban sao."""

    def test_returns_copy(self):
        """selected_paths tra ve copy, mutation khong anh huong original."""
        mgr = SelectionManager()
        mgr.add("/a.py")
        copy = mgr.selected_paths
        copy.add("/z.py")
        assert not mgr.is_selected("/z.py")
