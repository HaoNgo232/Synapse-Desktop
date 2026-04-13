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
import logging
import os
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger("synapse.mcp.config_installer")


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
    "Claude Code": {
        "config_path": "~/.claude.json",
        "root_key": "mcpServers",
        "extra_fields": {},
    },
    "Kiro CLI": {
        "config_path": "~/.kiro/settings/mcp.json",
        "root_key": "mcpServers",
        "extra_fields": {},
    },
    "OpenCode": {
        "config_path": "~/.config/opencode/opencode.json",
        "root_key": "mcp",
        "extra_fields": {},
        # OpenCode dung format khac: "type":"local", "command" la array thay vi tach command/args
        "format": "opencode",
    },
    "VS Code": {
        "config_path": ".vscode/mcp.json",
        "root_key": "servers",
        "extra_fields": {},
        "workspace_only": True,
    },
}

SERVER_NAME = "synapse"


# Ham _get_vscode_mcp_json_path tra ve duong dan file cau hinh MCP cua VS Code theo tung OS
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


# Ham get_mcp_command tu dong xac dinh lenh khoi chay mcp server dua tren moi truong (AppImage hoac script)
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
    main_script = (
        Path(__file__).resolve().parent.parent.parent
        / "presentation"
        / "main_window.py"
    )
    return [sys.executable, str(main_script), "--run-mcp"]


# Ham build_synapse_entry tao mot entry dictionary cho Synapse mcp server phu hop voi format cua tung client
def build_synapse_entry(target_name: str) -> dict:
    """Tao entry config cho Synapse MCP Server theo target cu the."""
    target = MCP_TARGETS[target_name]
    cmd = get_mcp_command()
    fmt = target.get("format", "standard")

    entry: dict = {}
    # Them cac truong dac thu cua target (vi du: "type":"stdio" cho Copilot)
    entry.update(target["extra_fields"])

    if fmt == "opencode":
        # OpenCode format: "type":"local", "command" la array gom ca executable + args
        entry["type"] = "local"
        entry["command"] = cmd
    else:
        # Standard format (Cursor, Claude Code, Kiro, Antigravity, ...):
        # "command" la executable, "args" la list cac tham so
        entry["command"] = cmd[0]
        entry["args"] = cmd[1:]

    return entry


# Ham get_config_path tra ve Path tuyet doi den file cau hinh cua target
def get_config_path(target_name: str, workspace_path: Optional[str] = None) -> Path:
    """Lay duong dan tuyet doi cua file config cho target.
    Neu workspace_path duoc cung cap, uu tien tao file local/workspace neu target ho tro.
    """
    target = MCP_TARGETS[target_name]

    # Neu target chi ho tro workspace-only (vd: VS Code Workspace)
    if target.get("workspace_only") and workspace_path:
        return Path(workspace_path) / target["config_path"]

    if workspace_path:
        # Phat hien custom workspace paths
        wp = Path(workspace_path)
        if target_name == "Cursor":
            return wp / ".cursor" / "mcp.json"
        elif target_name == "Antigravity":
            return wp / ".agent" / "mcp_config.json"
        elif target_name == "Claude Code":
            return wp / ".claude.json"  # Claude Code luon thuoc tinh theo folder

    raw = target["config_path"]
    if raw == "__vscode_mcp_json__":
        return _get_vscode_mcp_json_path()
    return Path(raw).expanduser()


# Ham read_existing_config doc file cau hinh JSON hien tai cua AI client
def read_existing_config(
    target_name: str, workspace_path: Optional[str] = None
) -> dict:
    """Doc file config hien tai. Tra ve dict rong neu file chua ton tai."""
    config_path = get_config_path(target_name, workspace_path)
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


# Ham merge_config ho tro merge cau hinh Synapse vao file config co san ma khong lam mat cac server khac
def merge_config(target_name: str, workspace_path: Optional[str] = None) -> dict:
    """Doc config hien tai va merge entry Synapse vao, giu nguyen cac server khac."""
    target = MCP_TARGETS[target_name]
    root_key = target["root_key"]
    existing = read_existing_config(target_name, workspace_path)

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


# Ham preview_json tao chuoi JSON da merge de hien thi cho nguoi dung kiem tra truoc khi cai dat
def preview_json(target_name: str, workspace_path: Optional[str] = None) -> str:
    """Tra ve JSON da merge de hien thi preview cho nguoi dung."""
    merged = merge_config(target_name, workspace_path)
    return json.dumps(merged, indent=2, ensure_ascii=False)


# Ham install_config thuc hien ghi de file cau hinh sau khi da merge
def install_config(
    target_name: str, workspace_path: Optional[str] = None
) -> tuple[bool, str]:
    """Ghi config da merge vao file. Tra ve (success, message)."""
    config_path = get_config_path(target_name, workspace_path)
    merged = merge_config(target_name, workspace_path)

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return True, f"Config saved to {config_path}"
    except OSError as e:
        return False, f"Failed to write config: {e}"


# Ham check_installed kiem tra xem Synapse mcp da duoc cau hinh trong client hay chua
def check_installed(target_name: str, workspace_path: Optional[str] = None) -> bool:
    """Kiem tra Synapse da duoc cai trong config cua target chua."""
    target = MCP_TARGETS[target_name]
    root_key = target["root_key"]
    existing = read_existing_config(target_name, workspace_path)

    if isinstance(root_key, str):
        root = existing.get(root_key, {})
    else:
        root = existing
        for k in root_key:
            if not isinstance(root, dict):
                return False
            root = root.get(k, {})

    return isinstance(root, dict) and SERVER_NAME in root


# Ham _needs_update kiem tra xem command trong config da cai co khac voi command hien tai khong
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

    fmt = target.get("format", "standard")
    if fmt == "opencode":
        # OpenCode: so sanh "command" (array) va "type"
        return current_entry.get("command") != new_entry.get(
            "command"
        ) or current_entry.get("type") != new_entry.get("type")
    else:
        # Standard: so sanh command (str) va args (list)
        return current_entry.get("command") != new_entry.get(
            "command"
        ) or current_entry.get("args") != new_entry.get("args")


# Ham auto_update_installed_configs tu dong cap nhat lai command trong cac config mcp neu app bi di chuyen
def auto_update_installed_configs() -> list[str]:
    """Tu dong cap nhat command trong tat ca config MCP da cai dat.

    Chi chay khi dang o frozen mode (AppImage/exe) vi khi dev, duong dan
    python + script khong thay doi. Voi AppImage, duong dan co the thay doi
    moi khi user di chuyen file .AppImage.

    Tra ve danh sach ten target da duoc cap nhat.

    An toan de goi moi lan app khoi dong - neu command khong doi thi
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
        except Exception as e:
            # Khong de loi auto-update lam crash app khoi dong, nhung log de de debug
            logger.warning("Auto-update failed for %s: %s", target_name, e)

    return updated
