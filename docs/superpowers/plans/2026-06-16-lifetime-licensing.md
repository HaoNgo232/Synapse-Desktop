# Lifetime Licensing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Support a lifetime (one-time purchase) licensing model by adding a `--lifetime` CLI flag to the generator, updating the settings view to display "Lifetime (Never Expires)", testing the changes, and updating the user guide.

**Architecture:** Extend the Ed25519 licensing tool and UI presentation layer to natively parse, format, and display `"never"` expiry dates.

**Tech Stack:** Python, PySide6, cryptography, pytest

---

### Task 1: Update License Generator Tool

**Files:**
- Modify: `tools/license_generator.py`

- [ ] **Step 1: Modify `sign_license` function signature and logic**
  Update `tools/license_generator.py` to add `lifetime: bool = False` argument to `sign_license`.
  Ensure `expiry_date` is set to `"never"` if `lifetime` is `True`.

  Replace `sign_license` function with:
  ```python
  def sign_license(license_id: str, email: str, days_valid: int, lifetime: bool = False) -> str:
      # Read private key
      private_key = serialization.load_pem_private_key(PRIVATE_KEY_PEM, password=None)
      if not isinstance(private_key, ed25519.Ed25519PrivateKey):
          raise ValueError("Key is not an Ed25519 private key")

      # Use UTC to calculate expiry date safely
      if lifetime:
          expiry_date = "never"
      else:
          expiry_date = (datetime.utcnow() + timedelta(days=days_valid)).strftime("%Y-%m-%d")

      payload = {
          "license_id": license_id,
          "email": email,
          "expiry_date": expiry_date,
          "product": "Synapse Desktop",
      }

      # Dump compactly with no extra spaces to keep the payload clean
      payload_str = json.dumps(payload, separators=(",", ":"))
      payload_bytes = payload_str.encode("utf-8")
      payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")

      # Sign the raw base64 payload bytes (just like verified in license_service.py)
      signature = private_key.sign(payload_b64.encode("utf-8"))
      signature_b64 = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")

      license_key = f"SYNAPSE-KEY.{payload_b64}.{signature_b64}"
      return license_key
  ```

- [ ] **Step 2: Add `--lifetime` CLI argument**
  Modify the `main` argument parsing logic in `tools/license_generator.py`.

  Replace `main` function with:
  ```python
  def main():
      parser = argparse.ArgumentParser(description="Synapse Desktop License Generator")
      parser.add_argument("--id", default="LIC-10001", help="License unique identifier")
      parser.add_argument(
          "--email", default="developer@synapse.com", help="Licensed email owner"
      )
      parser.add_argument("--days", type=int, default=365, help="Number of days valid")
      parser.add_argument(
          "--lifetime",
          action="store_true",
          help="Generate a lifetime license with no expiration",
      )
      parser.add_argument(
          "--keygen",
          action="store_true",
          help="Generate a new keypair instead of signing",
      )

      args = parser.parse_args()

      if args.keygen:
          generate_key_pair()
      else:
          key = sign_license(args.id, args.email, args.days, args.lifetime)
          print("=== GENERATED LICENSE KEY ===")
          print(key)
          print("=============================")
  ```

- [ ] **Step 3: Verify CLI functionality**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/python tools/license_generator.py --lifetime --id LIC-LIFE-01 --email lifetime@test.com`
  Expected: Command outputs a valid license key starting with `SYNAPSE-KEY.` and containing `"never"` in its base64 payload.

---

### Task 2: Update Settings View UI Formatting

**Files:**
- Modify: `presentation/views/settings/settings_view_qt.py`

- [ ] **Step 1: Modify `_update_license_display` function**
  Format `"never"` expiry date to `"Lifetime (Never Expires)"` for display.

  Replace `_update_license_display` in `presentation/views/settings/settings_view_qt.py` with:
  ```python
      def _update_license_display(self) -> None:
          settings = DomainRegistry.settings_service().load_settings()
          info = DomainRegistry.license_service().verify_license_key(settings.license_key)

          if info.is_valid:
              expiry_str = "Lifetime (Never Expires)" if info.expiry_date == "never" else info.expiry_date
              self._license_info_label.setText(
                  f"License ID: {info.license_id}\n"
                  f"Licensed Owner: {info.email}\n"
                  f"Valid Until: {expiry_str}\n"
                  f"Status: Active / Verified"
              )
              self._deactivate_btn.setEnabled(True)
          else:
              self._license_info_label.setText("Product is currently UNLICENSED.")
              self._deactivate_btn.setEnabled(False)
  ```

---

### Task 3: Write Lifetime License Unit Tests

**Files:**
- Modify: `tests/test_licensing.py`

- [ ] **Step 1: Add unit test class or method**
  Add a unit test checking verification of lifetime licenses.

  Append to `tests/test_licensing.py`:
  ```python
  def test_lifetime_license_verification():
      from infrastructure.adapters.license_service import Ed25519LicenseService
      from tools.license_generator import sign_license

      service = Ed25519LicenseService()
      
      # Generate and verify lifetime key
      lifetime_key = sign_license("LIC-LIFETIME-TEST", "lifetime@test.com", 365, lifetime=True)
      info = service.verify_license_key(lifetime_key)
      
      assert info.is_valid is True
      assert info.expiry_date == "never"
      assert info.email == "lifetime@test.com"
      assert info.license_id == "LIC-LIFETIME-TEST"
  ```

- [ ] **Step 2: Run pytest to verify unit tests pass**
  Run: `env -u PYTHONHOME -u PYTHONPATH .venv/bin/pytest tests/test_licensing.py -v`
  Expected: All 6 tests pass successfully.

---

### Task 4: Update Documentation

**Files:**
- Modify: `docs/HUONG_DAN_BAN_QUYEN.md`

- [ ] **Step 1: Add `--lifetime` explanation to guide**
  Modify `docs/HUONG_DAN_BAN_QUYEN.md` in the "Bước 3" section.

  Update lines 31-36:
  ```markdown
  * **Tạo Key có thời hạn 365 ngày (cho email `dev@test.com`):**
    ```bash
    env -u PYTHONHOME -u PYTHONPATH .venv/bin/python tools/license_generator.py --id LIC-DEV-99 --email dev@test.com --days 365
    ```

  * **Tạo Key trọn đời (Lifetime - Mua 1 lần):**
    ```bash
    env -u PYTHONHOME -u PYTHONPATH .venv/bin/python tools/license_generator.py --id LIC-LIFE-99 --email dev@test.com --lifetime
    ```
  ```

- [ ] **Step 2: Run Ruff, Pyrefly checking to ensure code linting/typing compliance**
  Run:
  ```bash
  env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff check --exclude tests/,stubs/,.agent/ --fix .
  env -u PYTHONHOME -u PYTHONPATH .venv/bin/ruff format .
  env -u PYTHONHOME -u PYTHONPATH .venv/bin/pyrefly check
  ```
  Expected: Formatting, linting, and type checking pass successfully without errors.
