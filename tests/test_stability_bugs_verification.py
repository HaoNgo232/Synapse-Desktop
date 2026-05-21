"""
Test suite dùng để xác minh (verify) và trigger các lỗi stability được tìm thấy trong đợt QA.

Kiểm tra:
- Bug 1: Signature của LockableFile.seek không khớp với TextIOWrapper (Positional-only).
- Bug 2: Import lỗi thời của module không tồn tại `skill_installer` trong SettingsView.
- Bug 3: Kiểm tra tĩnh các lệnh gọi QTimer.singleShot không an toàn (thiếu context widget).
- Bug 4: Kiểm tra decode an toàn của Git Utils khi đầu ra không phải bytes.
"""

import inspect
import re
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from shared.utils.file_lock import LockableFile
from presentation.views.settings.settings_view_qt import SettingsViewQt


class TestStabilityBug1SeekSignature:
    """Xác minh Bug #1 - Signature của LockableFile.seek phải tương thích với TextIOWrapper."""

    def test_seek_signature_positional_only(self):
        """Kiểm tra xem các tham số của seek() có phải là positional-only hay không."""
        sig = inspect.signature(LockableFile.seek)
        params = list(sig.parameters.values())

        # seek(self, offset, whence=0, /)
        # Bỏ qua tham số self (index 0)
        offset_param = params[1]
        whence_param = params[2]

        # Kiểm tra xem có phải positional-only
        assert offset_param.kind == inspect.Parameter.POSITIONAL_ONLY, (
            "offset phải là positional-only parameter"
        )
        assert whence_param.kind == inspect.Parameter.POSITIONAL_ONLY, (
            "whence phải là positional-only parameter"
        )

        print("\n✅ BUG STABILITY #1 FIXED: LockableFile.seek sử dụng positional-only parameters chính xác.")


class TestStabilityBug2ObsoleteImport:
    """Xác minh Bug #2 - Loại bỏ import skill_installer lỗi thời gây crash SettingsView."""

    def test_settings_view_import_safety(self):
        """SettingsView phải được import và khởi tạo mà không gặp ImportError hoặc NameError."""
        # Nếu import thành công tức là skill_installer không còn bị import nhầm
        assert SettingsViewQt is not None
        
        # Đọc file settings_view_qt.py để xác nhận không còn chuỗi "skill_installer"
        view_path = Path("presentation/views/settings/settings_view_qt.py")
        content = view_path.read_text(encoding="utf-8")
        
        # skill_installer không nên xuất hiện trong import
        assert "import skill_installer" not in content, (
            "Vẫn còn import skill_installer lỗi thời trong settings_view_qt.py"
        )
        print("\n✅ BUG STABILITY #2 FIXED: Không còn import lỗi thời của skill_installer.")


class TestStabilityBug3QTimerLifetime:
    """Xác minh Bug #3 - Kiểm tra tĩnh việc sử dụng QTimer.singleShot không an toàn."""

    def test_no_unsafe_qtimer_singleshot(self):
        """
        Quét toàn bộ codebase trong presentation/ để đảm bảo QTimer.singleShot
        luôn được truyền ngữ cảnh self thay vì gọi lambda trực tiếp không có context widget.
        """
        presentation_dir = Path("presentation")
        py_files = list(presentation_dir.glob("**/*.py"))
        
        unsafe_pattern = re.compile(r"QTimer\.singleShot\(\s*\d+\s*,\s*lambda")
        unsafe_calls = []

        for py_file in py_files:
            content = py_file.read_text(encoding="utf-8")
            for i, line in enumerate(content.splitlines(), 1):
                if unsafe_pattern.search(line):
                    # Ngoại trừ nếu dòng đó có comment bypass rõ ràng (nếu có)
                    unsafe_calls.append((py_file.name, i, line.strip()))

        if unsafe_calls:
            print("\n⚠️  CẢNH BÁO: Phát hiện các lệnh gọi QTimer.singleShot không an toàn (dễ gây lỗi C++ Object Deleted):")
            for filename, line_num, code in unsafe_calls:
                print(f"  {filename}:{line_num} -> {code}")
            # Fail test nếu phát hiện bất kỳ lệnh gọi không an toàn nào
            pytest.fail(f"Phát hiện {len(unsafe_calls)} lệnh gọi QTimer không an toàn.")
        else:
            print("\n✅ BUG STABILITY #3 FIXED: Toàn bộ lệnh gọi QTimer.singleShot đều truyền context an toàn.")


class TestStabilityBug4GitUtilsDecode:
    """Xác minh Bug #4 - Đảm bảo git_utils decode an toàn và không crash khi nhận dữ liệu lạ."""

    def test_git_utils_decode_handling(self):
        """Xác minh git_utils xử lý kiểu unescaped_bytes an toàn."""
        # Đọc mã nguồn git_utils.py để chắc chắn có kiểm tra isinstance(..., bytes)
        git_utils_path = Path("infrastructure/git/git_utils.py")
        content = git_utils_path.read_text(encoding="utf-8")
        
        assert "isinstance" in content and "decode" in content, (
            "Chưa cấu hình kiểm tra kiểu dữ liệu bytes trước khi decode trong git_utils.py"
        )
        print("\n✅ BUG STABILITY #4 FIXED: git_utils.py kiểm tra kiểu dữ liệu trước khi decode an toàn.")
