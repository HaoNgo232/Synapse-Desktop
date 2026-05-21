import sys
import os
import xml.etree.ElementTree as ET

# Thêm workspace root vào sys.path để import các module của dự án
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Import các module cần kiểm thử
from domain.prompt.opx_parser import parse_opx_response
from domain.workflow.test_analyzer import (
    format_test_analysis_xml,
    AnalysisResult,
    CoverageResult,
)
from domain.codemap.types import Symbol, SymbolKind

# Màu sắc để in terminal
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

print(
    f"{BLUE}=== BẮT ĐẦU CHẠY SCRIPT TRIGGER VÀ XÁC MINH LỖI (WORKFLOW ENGINE) ==={RESET}\n"
)

# =====================================================================
# TEST 1: OPX Parser Vulnerability (Missing Closing Tags & Silent Failure)
# =====================================================================
print(
    f"{YELLOW}[BUG 1] Kiểm tra lỗ hổng OPX Parser (Thiếu thẻ đóng gây silent failure){RESET}"
)

# Payload giả lập LLM trả về bị cắt cụt/thiếu thẻ đóng </edit> của block thứ nhất.
# Chú ý: Comment không được chứa chuỗi "</edit>" để tránh regex tự đóng nhầm.
malformed_opx_payload = """
<opx>
<edit op="patch" file="src/service_a.py">
  <find><![CDATA[<<<
  def start():
      print("Starting A")
  >>>]]></find>
  <put><![CDATA[<<<
  def start():
      print("Starting A v2")
  >>>]]></put>
  <!-- Thieu the dong o day -->

<edit op="patch" file="src/service_b.py">
  <find><![CDATA[<<<
  def stop():
      print("Stopping B")
  >>>]]></find>
  <put><![CDATA[<<<
  def stop():
      print("Stopping B v2")
  >>>]]></put>
</edit>
</opx>
"""

result = parse_opx_response(malformed_opx_payload)

print(f"Tổng số file actions được parsed: {len(result.file_actions)}")
if len(result.file_actions) == 1:
    print(
        f"{RED}[BUG DETECTED] Chỉ parse được 1 file action thay vì 2 do thiếu thẻ đóng! File src/service_b.py bị bỏ sót hoàn toàn.{RESET}"
    )
    action = result.file_actions[0]
    print(f"  - FileAction target duy nhất nhận được: {action.path}")
else:
    print(f"{GREEN}[INFO] Parser xử lý bình thường hoặc hành vi khác.{RESET}")

print("-" * 80 + "\n")


# =====================================================================
# TEST 2: Lỗi sinh XML Malformed (test_analyzer.py) do thiếu escaping
# =====================================================================
print(
    f"{YELLOW}[BUG 2] Lỗi sinh XML Malformed (test_analyzer.py) do thiếu escaping ký tự đặc biệt{RESET}"
)

# Giả lập AnalysisResult chứa symbol có chứa dấu ngoặc kép trong signature
# ví dụ: def connect(host="localhost", port=8080)
bad_symbol = Symbol(
    name="connect",
    kind=SymbolKind.FUNCTION,
    file_path="src/db.py",
    line_start=15,
    line_end=20,
    signature='connect(host="localhost", port=8080)',
    parent="",
)

coverage_res = CoverageResult(
    source_file="src/db.py",
    test_files=[],
    tested_symbols={},
    untested_symbols=[bad_symbol],
    coverage_pct=0.0,
    priority_symbols=[bad_symbol],
)

analysis_res = AnalysisResult(
    file_coverages=[coverage_res],
    existing_test_files=[],
    suggested_test_files=["tests/test_db.py"],
    total_symbols=1,
    total_untested=1,
    analysis_summary="0/1 symbols tested",
)

# Render XML
generated_xml = format_test_analysis_xml(analysis_res)
print("XML được tạo ra:")
print(generated_xml)

# Thử parse XML bằng ElementTree để kiểm tra tính hợp lệ
try:
    # Wrap in root tag để parse
    full_xml = f"<root>{generated_xml}</root>"
    ET.fromstring(full_xml)
    print(f"{GREEN}[SUCCESS] XML hợp lệ.{RESET}")
except ET.ParseError as e:
    print(f"{RED}[BUG DETECTED] XML bị Malformed! Lỗi: {e}{RESET}")

print(f"\n{BLUE}=== KẾT THÚC CHẠY SCRIPT XÁC MINH LỖI ==={RESET}")
