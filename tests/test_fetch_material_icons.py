import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import zipfile
import shutil

def test_fetch_icons_success():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        output_dir = tmp_path / "material-icons"
        
        # Create a mock ZIP file (VSIX)
        zip_file = tmp_path / "extension.vsix"
        with zipfile.ZipFile(zip_file, "w") as zf:
            zf.writestr("extension/dist/material-icons.json", '{"iconDefinitions": {}}')
            zf.writestr("extension/icons/python.svg", "<svg></svg>")
            
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = zip_file.read_bytes()
        
        with patch("requests.get", return_value=mock_response):
            from scripts.fetch_material_icons import fetch_icons
            result = fetch_icons(output_dir, force=True)
            
        assert result is True
        assert (output_dir / "material-icons.json").exists()
        assert (output_dir / "icons" / "python.svg").exists()
