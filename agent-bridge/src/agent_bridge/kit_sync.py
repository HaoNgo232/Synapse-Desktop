import os
import shutil
import subprocess
import tempfile
from pathlib import Path

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'

KIT_REPO_URL = "https://github.com/vudovn/antigravity-kit"

def update_kit(target_dir: str):
    target_path = Path(target_dir).resolve()
    print(f"{Colors.HEADER}🔄 Updating Antigravity Kit from {KIT_REPO_URL}...{Colors.ENDC}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        try:
            print(f"{Colors.BLUE}  📥 Cloning repository...{Colors.ENDC}")
            subprocess.run(["git", "clone", "--depth", "1", KIT_REPO_URL, str(tmp_path)], check=True, capture_output=True)
            
            repo_agent_dir = tmp_path / ".agent"
            if not repo_agent_dir.exists():
                # Try root if .agent folder doesn't exist (depending on repo structure)
                repo_agent_dir = tmp_path

            print(f"{Colors.BLUE}  📂 Syncing agents and skills...{Colors.ENDC}")
            
            for sub in ["agents", "skills", "workflows"]:
                src = repo_agent_dir / sub
                dst = target_path / sub
                
                if src.exists():
                    if not dst.exists():
                        dst.mkdir(parents=True)
                    
                    # Merge content
                    for item in src.iterdir():
                        dest_item = dst / item.name
                        if item.is_dir():
                            if dest_item.exists():
                                shutil.rmtree(dest_item)
                            shutil.copytree(item, dest_item)
                        else:
                            shutil.copy2(item, dest_item)
                    print(f"{Colors.GREEN}    ✅ Sync {sub} complete.{Colors.ENDC}")

            print(f"{Colors.GREEN}✨ Antigravity Kit is now up to date!{Colors.ENDC}")
            print(f"{Colors.YELLOW}🔔 Note: You may want to run 'agent-bridge kiro' or 'agent-bridge copilot' to update your IDE configs.{Colors.ENDC}")

        except subprocess.CalledProcessError as e:
            print(f"{Colors.RED}❌ Failed to clone repository: {e.stderr.decode()}{Colors.ENDC}")
        except Exception as e:
            print(f"{Colors.RED}❌ Error during sync: {e}{Colors.ENDC}")
