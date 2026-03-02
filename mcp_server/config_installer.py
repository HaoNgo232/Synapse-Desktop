"""
MCP Config Installer - Tu dong cai dat cau hinh MCP Server vao cac AI clients.

Ho tro:
- Cursor:              ~/.cursor/mcp.json                    (workspace/global)
- GitHub Copilot:      VS Code User mcp.json (servers)       (user-level)
- GitHub Copilot CLI:  ~/.copilot/mcp-config.json            (global)
- Antigravity:         ~/.gemini/antigravity/mcp_config.json

Moi target deu:
1. Doc file config hien tai (neu co)
2. Merge/replace chi muc "synapse" ma khong anh huong cac MCP server khac
3. Hien preview JSON truoc khi ghi de nguoi dung kiem tra
"""

import json
import os
import sys
from pathlib import Path


# Dinh nghia cac AI client duoc ho tro
# root_key:
#   - Neu la str: key cha chua danh sach MCP servers trong file JSON (vd: "mcpServers")
#   - Neu la list[str]: duong dan long nhau (vd: ["mcp", "mcpServers"] cho nested keys)
# extra_fields: cac truong them vao entry "synapse" (vi du Copilot can "type":"stdio")
MCP_TARGETS: dict[str, dict] = {
    "Cursor": {
        "config_path": "~/.cursor/mcp.json",
        "root_key": "mcpServers",
        "extra_fields": {},
    },
    "Antigravity": {
        "config_path": "~/.gemini/antigravity/mcp_config.json",
        "root_key": "mcpServers",
        "extra_fields": {},
    },
}

SERVER_NAME = "synapse"


def _get_vscode_mcp_json_path() -> Path:
    """Tra ve duong dan toi VS Code User mcp.json theo OS.

    Day la file cau hinh MCP rieng biet o user-level (KHONG phai settings.json).
    Duong dan:
      - Windows: %APPDATA%/Code/User/mcp.json
      - macOS:   ~/Library/Application Support/Code/User/mcp.json
      - Linux:   ~/.config/Code/User/mcp.json
    """
    home = Path.home()

    if sys.platform.startswith("win"):
        appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        return appdata / "Code" / "User" / "mcp.json"

    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Code" / "User" / "mcp.json"

    # Mac dinh: Linux / Unix
    return home / ".config" / "Code" / "User" / "mcp.json"


def get_mcp_command() -> list[str]:
    """Tu dong phat hien lenh khoi chay MCP Server."""
    if getattr(sys, "frozen", False):
        # AppImage dat APPIMAGE, dung path nay de spawn lai sau nay
        appimage_path = os.environ.get("APPIMAGE")
        if appimage_path:
            return [appimage_path, "--run-mcp"]

        # Truong hop PyInstaller .exe hoac build khac: sys.executable la duong dan on dinh
        return [sys.executable, "--run-mcp"]

    # Chay qua python script
    main_script = Path(__file__).resolve().parent.parent / "main_window.py"
    return [sys.executable, str(main_script), "--run-mcp"]


def build_synapse_entry(target_name: str) -> dict:
    """Tao entry config cho Synapse MCP Server theo target cu the."""
    target = MCP_TARGETS[target_name]
    cmd = get_mcp_command()

    entry: dict = {}
    # Them cac truong dac thu cua target (vi du: "type":"stdio" cho Copilot)
    entry.update(target["extra_fields"])
    entry["command"] = cmd[0]
    entry["args"] = cmd[1:]

    return entry


def get_config_path(target_name: str) -> Path:
    """Lay duong dan tuyet doi cua file config cho target."""
    raw = MCP_TARGETS[target_name]["config_path"]
    if raw == "__vscode_mcp_json__":
        return _get_vscode_mcp_json_path()
    return Path(raw).expanduser()


def read_existing_config(target_name: str) -> dict:
    """Doc file config hien tai. Tra ve dict rong neu file chua ton tai."""
    config_path = get_config_path(target_name)
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def merge_config(target_name: str) -> dict:
    """Doc config hien tai va merge entry Synapse vao, giu nguyen cac server khac."""
    target = MCP_TARGETS[target_name]
    root_key = target["root_key"]
    existing = read_existing_config(target_name)

    # Chuan hoa root path thanh list de ho tro nested keys (vd: ["mcp", "mcpServers"])
    if isinstance(root_key, str):
        keys: list[str] = [root_key]
    else:
        keys = list(root_key)

    # Di chuyen den dict la ma chua danh sach servers
    node: dict = existing
    for k in keys[:-1]:
        child = node.get(k)
        if not isinstance(child, dict):
            child = {}
            node[k] = child
        node = child

    leaf_key = keys[-1]
    leaf = node.get(leaf_key)
    if not isinstance(leaf, dict):
        leaf = {}
        node[leaf_key] = leaf

    # Ghi de chi muc "synapse", giu nguyen cac server khac
    leaf[SERVER_NAME] = build_synapse_entry(target_name)

    return existing


def preview_json(target_name: str) -> str:
    """Tra ve JSON da merge de hien thi preview cho nguoi dung."""
    merged = merge_config(target_name)
    return json.dumps(merged, indent=2, ensure_ascii=False)


def install_config(target_name: str) -> tuple[bool, str]:
    """Ghi config da merge vao file. Tra ve (success, message)."""
    config_path = get_config_path(target_name)
    merged = merge_config(target_name)

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return True, f"Config saved to {config_path}"
    except OSError as e:
        return False, f"Failed to write config: {e}"


def check_installed(target_name: str) -> bool:
    """Kiem tra Synapse da duoc cai trong config cua target chua."""
    target = MCP_TARGETS[target_name]
    root_key = target["root_key"]
    existing = read_existing_config(target_name)

    if isinstance(root_key, str):
        root = existing.get(root_key, {})
    else:
        root = existing
        for k in root_key:
            if not isinstance(root, dict):
                return False
            root = root.get(k, {})

    return isinstance(root, dict) and SERVER_NAME in root


def _needs_update(target_name: str) -> bool:
    """Kiem tra config da cai co dang tro den command hien tai khong.

    Tra ve True neu command trong file config KHAC voi command hien tai
    (vi du: user da di chuyen file AppImage sang vi tri khac).
    """
    target = MCP_TARGETS[target_name]
    root_key = target["root_key"]
    existing = read_existing_config(target_name)

    # Di chuyen den node chua danh sach servers
    if isinstance(root_key, str):
        servers = existing.get(root_key, {})
    else:
        servers = existing
        for k in root_key:
            if not isinstance(servers, dict):
                return False
            servers = servers.get(k, {})

    if not isinstance(servers, dict) or SERVER_NAME not in servers:
        return False

    current_entry = servers[SERVER_NAME]
    new_entry = build_synapse_entry(target_name)

    # So sanh command va args — neu khac thi can update
    return current_entry.get("command") != new_entry.get(
        "command"
    ) or current_entry.get("args") != new_entry.get("args")


def auto_update_installed_configs() -> list[str]:
    """Tu dong cap nhat command trong tat ca config MCP da cai dat.

    Chi chay khi dang o frozen mode (AppImage/exe) vi khi dev, duong dan
    python + script khong thay doi. Voi AppImage, duong dan co the thay doi
    moi khi user di chuyen file .AppImage.

    Tra ve danh sach ten target da duoc cap nhat.

    An toan de goi moi lan app khoi dong — neu command khong doi thi
    khong ghi file nao ca.
    """
    if not getattr(sys, "frozen", False):
        # Khong can auto-update khi chay dev mode
        return []

    updated: list[str] = []
    for target_name in MCP_TARGETS:
        try:
            if not check_installed(target_name):
                continue
            if not _needs_update(target_name):
                continue

            success, _ = install_config(target_name)
            if success:
                updated.append(target_name)
        except Exception:
            # Khong de loi auto-update lam crash app khoi dong
            pass

    return updated
