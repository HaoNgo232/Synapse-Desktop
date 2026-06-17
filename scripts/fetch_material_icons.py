import os
import sys
import zipfile
from pathlib import Path
import io
import requests

VSIX_URL = "https://marketplace.visualstudio.com/_apis/public/gallery/publishers/PKief/vsextensions/material-icon-theme/latest/vspackage"

def fetch_icons(output_dir: Path, force: bool = False) -> bool:
    if output_dir.exists() and (output_dir / "material-icons.json").exists() and not force:
        print("Material icons already exist. Skipping download.")
        return True

    print(f"Downloading VS Code Material Icon Theme from {VSIX_URL}...")
    try:
        response = requests.get(VSIX_URL, timeout=30)
        if response.status_code != 200:
            print(f"Failed to download: HTTP {response.status_code}")
            return False
        
        # VSIX is a ZIP file. Read it in memory.
        zip_data = io.BytesIO(response.content)
        with zipfile.ZipFile(zip_data) as zf:
            # Create directories
            output_dir.mkdir(parents=True, exist_ok=True)
            icons_dir = output_dir / "icons"
            icons_dir.mkdir(parents=True, exist_ok=True)
            
            # Extract relevant files
            for file_info in zf.infolist():
                name = file_info.filename
                if name == "extension/dist/material-icons.json":
                    content = zf.read(file_info)
                    with open(output_dir / "material-icons.json", "wb") as f:
                        f.write(content)
                elif name.startswith("extension/icons/") and name.endswith(".svg"):
                    content = zf.read(file_info)
                    filename = Path(name).name
                    with open(icons_dir / filename, "wb") as f:
                        f.write(content)
                        
        print("Successfully extracted material icons.")
        return True
    except Exception as e:
        print(f"Error fetching icons: {e}")
        return False

if __name__ == "__main__":
    script_dir = Path(__file__).parent.parent
    dest = script_dir / "assets" / "material-icons"
    fetch_icons(dest, force="--force" in sys.argv)
