import subprocess
import sys
import pytest
from infrastructure.adapters.subprocess_utils import run_subprocess


def test_run_subprocess_utf8_encoding(tmp_path):
    script = tmp_path / "print_utf8.py"
    # Ghi bytes UTF-8 thô lên stdout để tránh lỗi python print encoding trên Windows console
    script.write_text(
        "import sys\n"
        "sys.stdout.buffer.write('Xin chào, đây là UTF-8: \u008f'.encode('utf-8'))\n",
        encoding="utf-8",
    )

    # Chạy với text=True, nếu không có encoding="utf-8" mặc định trên Windows (cp1252),
    # nó sẽ ném ra UnicodeDecodeError trong luồng đọc của subprocess.
    try:
        result = run_subprocess(
            [sys.executable, str(script)], capture_output=True, text=True, check=True
        )
        # Nếu không lỗi thì kiểm tra stdout
        assert "Xin chào" in result.stdout
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Subprocess failed with error: {e.stderr}")
