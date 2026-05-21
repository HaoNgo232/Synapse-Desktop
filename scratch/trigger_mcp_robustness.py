import sys
import json
from pathlib import Path
import shutil

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from domain.selection.provenance import SelectionState
from domain.selection.selection_reader import read_selection_state
from infrastructure.mcp.core.session_manager import SessionManager
from infrastructure.mcp.config_installer import (
    install_config,
    read_existing_config,
)


def test_corrupted_selection_json_data_loss():
    print("=== Testing Scenario 3: Malformed JSON selection file robustness ===")

    # Setup temporary directory and mock selection file
    temp_dir = Path(__file__).resolve().parent.parent / "scratch_temp_mcp"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True)

    session_file = temp_dir / "selection.json"

    # 1. Write valid selection
    initial_state = SelectionState()
    initial_state.add_paths(["src/existing_file.py"], "user")
    session_file.write_text(
        json.dumps(initial_state.to_dict(), indent=2), encoding="utf-8"
    )
    print(f"1. Wrote initial valid selection to {session_file.name}")
    print(f"   Current content: {session_file.read_text().strip()}")

    # 2. Corrupt the file (make it invalid JSON)
    session_file.write_text("{invalid_json: true, paths: [", encoding="utf-8")
    print("2. Corrupted the selection file with malformed JSON")

    # 3. Read selection state
    parsed_state = read_selection_state(session_file)
    print(
        f"3. Parsed selection state: version={parsed_state.version}, paths={parsed_state.paths}"
    )
    print(
        "   Note: The parser silently caught the JSONDecodeError and returned an empty state."
    )

    # 4. Perform an 'add' operation via SessionManager
    # SessionManager.add_selection resolves paths against workspace. Let's make sure the added file exists.
    added_file = temp_dir / "new_file.py"
    added_file.write_text("# new file", encoding="utf-8")

    print("4. Performing add_selection on corrupted file...")
    result = SessionManager.add_selection(session_file, temp_dir, ["new_file.py"])
    print(f"   Result message: {result}")

    # 5. Show what happens to the file
    final_content = session_file.read_text().strip()
    print(f"5. Final selection file content after addition:\n{final_content}")

    if "existing_file.py" not in final_content:
        print(
            "[POTENTIAL BUG] Silent data loss! The original selection 'existing_file.py' was completely lost because the corrupted JSON was silently parsed as empty, and then overwritten."
        )
    else:
        print("[OK] Original selection preserved.")

    if temp_dir.exists():
        shutil.rmtree(temp_dir)


def test_corrupted_config_json_data_loss():
    print(
        "\n=== Testing Scenario 4: Malformed Cursor config_installer.py JSON data loss ==="
    )

    # Setup temporary directory and mock mcp.json file
    temp_dir = Path(__file__).resolve().parent.parent / "scratch_temp_config"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True)

    # The config path for target "Cursor" is workspace/.cursor/mcp.json when workspace_path is passed
    config_file = temp_dir / ".cursor" / "mcp.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)

    # 1. Write initial configuration containing other servers
    initial_config = {
        "mcpServers": {
            "other-useful-server": {"command": "node", "args": ["some-server.js"]}
        }
    }
    config_file.write_text(json.dumps(initial_config, indent=2), encoding="utf-8")
    print(f"1. Wrote initial mcp.json with other servers: {config_file}")

    # 2. Corrupt the configuration file
    config_file.write_text("{mcpServers: { ...corrupted...", encoding="utf-8")
    print("2. Corrupted the configuration file")

    # 3. Read it using config_installer helper
    existing = read_existing_config("Cursor", str(temp_dir))
    print(f"3. Read existing configuration: {existing}")

    # 4. Attempt to install synapse config
    print("4. Installing synapse config onto the corrupted file...")
    success, msg = install_config("Cursor", str(temp_dir))
    print(f"   Success: {success}, Message: {msg}")

    # 5. Check final content
    final_content = config_file.read_text().strip()
    print(f"5. Final configuration file content:\n{final_content}")

    if "other-useful-server" not in final_content:
        print(
            "[POTENTIAL BUG] Critical data loss! All other configured MCP servers were wiped out because the corrupted JSON configuration was silently ignored and overwritten."
        )
    else:
        print("[OK] Other MCP servers preserved.")

    if temp_dir.exists():
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    test_corrupted_selection_json_data_loss()
    test_corrupted_config_json_data_loss()
