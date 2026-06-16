# Lifetime Licensing Design Spec

This specification outlines the design changes required to officially support a lifetime (one-time purchase) license model in Synapse Desktop.

## 1. Goal
Support lifetime licenses where the `expiry_date` is set to `"never"`. The license generator tool should allow creating such licenses via a `--lifetime` CLI flag, the settings UI should display the expiration as `"Lifetime (Never Expires)"` instead of `"never"`, and proper unit tests must cover this scenario.

## 2. Proposed Changes

### Developer Tools
- **[MODIFY] `tools/license_generator.py`**:
  - Add a `--lifetime` CLI flag to the argument parser.
  - Modify `sign_license` to accept `days_valid: Optional[int] = None` or add a `lifetime: bool = False` argument.
  - If `lifetime` is true, write `"expiry_date": "never"` in the payload JSON. Otherwise, calculate the expiration date using `days_valid`.

### Presentation Layer
- **[MODIFY] `presentation/views/settings/settings_view_qt.py`**:
  - Update `_update_license_display()` to format `"never"` nicely:
    ```python
    expiry_str = "Lifetime (Never Expires)" if info.expiry_date == "never" else info.expiry_date
    ```
  - Display `Valid Until: Lifetime (Never Expires)` when a lifetime license is active.

### Verification and Testing
- **[MODIFY] `tests/test_licensing.py`**:
  - Add `test_lifetime_license_verification()` unit test to verify that a lifetime license generated with `"expiry_date": "never"` is parsed and verified successfully.

### Documentation
- **[MODIFY] `docs/HUONG_DAN_BAN_QUYEN.md`**:
  - Add guidance on generating lifetime keys using the `--lifetime` flag.

## 3. Verification Plan

### Automated Tests
- Run the new test case along with existing tests:
  ```bash
  env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/test_licensing.py -v
  ```

### Manual Verification
1. Run the license generator with the `--lifetime` flag:
   ```bash
   env -u PYTHONHOME -u PYTHONPATH .venv/bin/python tools/license_generator.py --lifetime --email customer@example.com
   ```
2. Launch the app (`./start.sh`), paste the generated key, and ensure activation succeeds.
3. Open Settings and check that the license status is displayed as `Valid Until: Lifetime (Never Expires)`.
