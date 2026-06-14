# Template Registry and Tier Logic Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sửa template registry trong `domain/prompt/template_manager.py` để chỉ expose 7 templates thiết yếu, loại bỏ hoàn toàn tier logic (lite/pro) đồng thời duy trì tính tương thích ngược cho các hàm gọi.

**Architecture:** Cấu trúc lại `BuiltInTemplateProvider` để lọc registry chỉ còn 7 templates mặc định, xóa bỏ các hàm `_get_template_tier` và logic rẽ nhánh tier trong `load_template()`. Các hàm load sẽ luôn đọc từ file pro (file MD nằm trực tiếp trong thư mục templates). Để đảm bảo tính tương thích ngược, hàm `load_template` ở cả provider lẫn module level sẽ nhận thêm tham số `tier` và bỏ qua nó mà không crash.

**Tech Stack:** Python, PySide6, Pytest

---

### Task 1: Tạo Tests TDD Cho Template Registry Mới

**Files:**
- Create: [test_template_registry.py](file:///home/hao/Desktop/labs/Synapse-Desktop/tests/domain/prompt/test_template_registry.py)

- [ ] **Step 1: Viết 6 test case rỗng theo đúng quy định TDD**
  Tạo file `tests/domain/prompt/test_template_registry.py` chứa 6 test case với thân hàm chỉ là `pass`.
  
  ```python
  import pytest
  from domain.prompt.template_manager import (
      list_templates,
      load_template,
      get_template_info,
  )

  def test_list_returns_exactly_7_builtin():
      pass

  def test_load_template_no_longer_needs_tier():
      pass

  def test_custom_templates_unaffected():
      pass

  def test_removed_template_ids_raise_key_error():
      pass

  def test_lite_dir_not_loaded():
      pass

  def test_all_7_templates_have_content():
      pass
  ```

- [ ] **Step 2: Viết logic cụ thể cho các bài kiểm tra này để chúng FAIL khi chạy trên codebase hiện tại**
  Cập nhật file `tests/domain/prompt/test_template_registry.py` với nội dung logic thực tế:

  ```python
  import pytest
  from pathlib import Path
  from domain.prompt.template_manager import (
      list_templates,
      load_template,
      get_template_info,
      CUSTOM_TEMPLATES_DIR,
  )

  def test_list_returns_exactly_7_builtin():
      builtin = [t for t in list_templates() if not t.is_custom]
      assert len(builtin) == 7
      expected_ids = {
          "bug_hunter",
          "security_auditor",
          "architecture_reviewer",
          "code_explainer",
          "test_writer",
          "performance_optimizer",
          "doc_generator",
      }
      assert {t.template_id for t in builtin} == expected_ids

  def test_load_template_no_longer_needs_tier():
      # Gọi với tier hay không tier đều trả về cùng 1 nội dung
      content_default = load_template("bug_hunter")
      content_lite = load_template("bug_hunter", tier="lite")
      content_pro = load_template("bug_hunter", tier="pro")
      assert content_default == content_lite
      assert content_default == content_pro

  def test_custom_templates_unaffected(tmp_path, monkeypatch):
      import domain.prompt.template_manager as tm
      monkeypatch.setattr(tm, "CUSTOM_TEMPLATES_DIR", tmp_path)
      from domain.prompt.template_manager import LocalCustomTemplateProvider
      
      custom_file = tmp_path / "custom_test.md"
      custom_file.write_text("Custom Content", encoding="utf-8")
      
      provider = LocalCustomTemplateProvider()
      assert provider.handles("custom_test")
      assert provider.load_template("custom_test") == "Custom Content"

  def test_removed_template_ids_raise_key_error():
      # Ví dụ template "refactoring_expert" đã bị xóa khỏi registry
      with pytest.raises(KeyError):
          load_template("refactoring_expert")

  def test_lite_dir_not_loaded():
      import domain.prompt.template_manager as tm
      # Đảm bảo không load từ thư mục lite
      lite_file = tm._TEMPLATES_DIR / "lite" / "bug_hunter.md"
      if lite_file.exists():
          content_lite_file = lite_file.read_text(encoding="utf-8").strip()
          content_loaded = load_template("bug_hunter")
          assert content_loaded != content_lite_file

  def test_all_7_templates_have_content():
      expected_ids = [
          "bug_hunter",
          "security_auditor",
          "architecture_reviewer",
          "code_explainer",
          "test_writer",
          "performance_optimizer",
          "doc_generator",
      ]
      for tid in expected_ids:
          content = load_template(tid)
          assert len(content) > 0
  ```

- [ ] **Step 3: Chạy pytest để xác nhận các bài test FAIL**
  Chạy lệnh:
  ```bash
  env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/domain/prompt/test_template_registry.py -v
  ```
  Mong đợi: Lỗi assert `len(builtin) == 7` (hiện tại trả về 16) hoặc lỗi khác chứng minh test đang FAIL.

---

### Task 2: Cấu trúc lại file template_manager.py

**Files:**
- Modify: [template_manager.py](file:///home/hao/Desktop/labs/Synapse-Desktop/domain/prompt/template_manager.py)

- [ ] **Step 1: Sửa đổi registry chỉ còn lại 7 template mặc định, xóa logic tier**
  - Xóa tất cả các template khác ngoài 7 template yêu cầu trong `BuiltInTemplateProvider._registry`.
  - Loại bỏ hoàn toàn hàm `_get_template_tier()`.
  - Loại bỏ biến `_LITE_OUTPUT_FORMAT_PATH`.
  - Sửa đổi `BuiltInTemplateProvider.load_template` nhận `tier: str = None` (hoặc `*args, **kwargs`) để ignore nó và luôn load từ file Pro: `_TEMPLATES_DIR / f"{template_id}.md"`.
  - Sửa đổi hàm `load_template` ở module level: `def load_template(template_id: str, opx_mode: bool = False, tier: str = None, *args, **kwargs) -> str:`.
  - Sửa đổi `_get_output_format_only()` để luôn sử dụng `_OUTPUT_FORMAT_PATH`.

- [ ] **Step 2: Chạy lại bài test mới tạo để đảm bảo PASS**
  Chạy lệnh:
  ```bash
  env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/domain/prompt/test_template_registry.py -v
  ```
  Mong đợi: Tất cả 6 test case vừa tạo PASS.

- [ ] **Step 3: Commit các thay đổi ban đầu**
  Chạy lệnh:
  ```bash
  git add domain/prompt/template_manager.py tests/domain/prompt/test_template_registry.py
  git commit -m "feat: restrict registry to 7 templates and remove tier logic"
  ```

---

### Task 3: Cập nhật Callers trong UI và Tests Cũ

**Files:**
- Modify: [context_view_qt.py](file:///home/hao/Desktop/labs/Synapse-Desktop/presentation/views/context/context_view_qt.py)
- Modify: [ui_builder.py](file:///home/hao/Desktop/labs/Synapse-Desktop/presentation/views/context/ui_builder.py)
- Modify: [test_template_manager.py](file:///home/hao/Desktop/labs/Synapse-Desktop/tests/test_template_manager.py)
- Modify: [test_template_ui.py](file:///home/hao/Desktop/labs/Synapse-Desktop/tests/ui/test_template_ui.py)

- [ ] **Step 1: Cập nhật UI components để xóa bỏ hiển thị liên quan đến Tier**
  - Trong `ui_builder.py`, sửa button `_template_btn` text thành `"Templates"`, loại bỏ biến `current_tier` và `tier_label`.
  - Trong `context_view_qt.py`, tại `_populate_template_menu`, loại bỏ việc tạo và chèn `TierSelector` vào menu. Loại bỏ phương thức `_on_tier_changed`.
  
- [ ] **Step 2: Cập nhật các bài test cũ để tương thích với cấu trúc mới**
  - Trong `tests/test_template_manager.py`:
    - Cập nhật danh sách `required` templates trong `test_has_expected_templates` để khớp với 7 templates còn lại (xóa `tech_debt_analyzer`, `ui_ux_reviewer`, ...).
    - Xóa các bài test liên quan đến `tier` như `test_can_force_pro_tier` và `test_lite_fallback_to_pro_when_lite_missing`.
  - Trong `tests/ui/test_template_ui.py`:
    - Xóa test `test_tier_selector_in_menu` vì `TierSelector` không còn được chèn vào menu nữa.

- [ ] **Step 3: Chạy toàn bộ các bài test liên quan để xác nhận PASS**
  Chạy lệnh:
  ```bash
  env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/test_template_manager.py tests/ui/test_template_ui.py -v
  ```
  Mong đợi: Tất cả các bài test cũ hoạt động bình thường và PASS.

- [ ] **Step 4: Commit thay đổi UI và tests**
  Chạy lệnh:
  ```bash
  git add presentation/views/context/context_view_qt.py presentation/views/context/ui_builder.py tests/test_template_manager.py tests/ui/test_template_ui.py
  git commit -m "refactor: remove TierSelector from UI and update existing tests"
  ```

---

### Task 4: Chạy toàn bộ Test Suite và Xác nhận Hoàn thành

- [ ] **Step 1: Chạy toàn bộ test suite để đảm bảo không có regression**
  Chạy lệnh:
  ```bash
  env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/ -v
  ```
  Mong đợi: Tất cả các test trong codebase đều PASS.

- [ ] **Step 2: Thực hiện linting và type checking để đảm bảo chất lượng code**
  Chạy lệnh:
  ```bash
  env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff check --fix .
  env -u PYTHONHOME -u PYTHONPATH .venv/bin/pyrefly check
  ```
  Mong đợi: Không có lỗi linting hay type checking nào xuất hiện.
