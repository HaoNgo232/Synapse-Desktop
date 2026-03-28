"""
Metadata Extraction Utils - Ho tro trich xuat layer, role tu file path va content.
Tach ra file rieng de de quan ly cac tap hop tu khoa (heuristics) cho nhieu kien truc.
"""

from pathlib import Path
from typing import Optional, Set

# Danh sach cac folder duoc coi la "Layer" phan chia kien truc
# Ho tro: DDD, Clean Architecture, Web (React, Next.js, Vue), Backend (Express, Django, Flask)
ARCH_LAYERS: Set[str] = {
    # --- Clean Architecture / DDD ---
    "application",
    "domain",
    "infrastructure",
    "presentation",
    "shared",
    "core",
    "interfaces",
    "use_cases",
    "entities",
    # --- Web Frontend (React, Next.js, Vue) ---
    "hooks",
    "services",
    "features",
    "modules",
    "components",
    "pages",
    "api",
    "store",
    "actions",
    "reducers",
    "providers",
    "contexts",
    "styles",
    "public",
    "app",
    # --- Backend (Express, Django, Flask, FastAPI) ---
    "routes",
    "controllers",
    "models",
    "schemas",
    "services",
    "repositories",
    "migrations",
    "serializers",
    "views",
    "templates",
    "middlewares",
    "db",
    # --- General / Languages (Python, Rust, Java, Go) ---
    "utils",
    "config",
    "scripts",
    "tests",
    "stubs",
    "assets",
    "crates",  # Rust
    "modules",  # Rust/C++
    "target",  # Rust/Java build
    "java",  # Java src root
    "resources",  # Java/Web assets
    "test",  # Java/JS tests
    # Note: 'src', 'lib' thuong la folder to chuc cap cao,
    # khong nen coi la layer neu co layer con (e.g. src/domain -> domain).
}


def extract_layer_from_path(
    rel_path: str, workspace_root: Optional[Path] = None
) -> Optional[str]:
    """
    Trich xuat layer tu path dua tren danh sach heuristics ARCH_LAYERS.

    Args:
        rel_path: Duong dan file (co the la tuyet doi hoac tuong doi)
        workspace_root: Thu muc goc de convert sang relative neu can

    Returns:
        Ten layer (folder) neu tim thay trong ARCH_LAYERS, nguoc lai None.
    """
    # Neu path la absolute va co workspace_root, convert sang relative truoc
    if workspace_root:
        try:
            p = Path(rel_path)
            if p.is_absolute():
                rel_path = str(p.resolve().relative_to(workspace_root.resolve()))
        except (ValueError, RuntimeError):
            pass

    # Normalize path separator va split
    # replace('\\', '/') de ho tro Windows path trong moi truong Linux/Web
    parts = rel_path.replace("\\", "/").lstrip("/").split("/")

    if len(parts) > 0:
        # Check tung phan tu trong path tu trai sang phai
        # Uu tien cac folder cap cao hon (gan root hon)
        for part in parts:
            if part.lower() in ARCH_LAYERS:
                return part.lower()
    return None


def extract_role_from_content(path: Path, content: str) -> Optional[str]:
    """Doan role cua file dua tren class name hoac file name suffix."""
    import re

    # 1. Tim class name chinh trong file
    class_match = re.search(r"^class\s+([A-Z]\w+)", content, re.MULTILINE)
    if class_match:
        return class_match.group(1)

    # 2. Fallback vao suffix cua file name
    stem = path.stem
    if "_" in stem:
        parts = stem.split("_")
        return "".join(p.capitalize() for p in parts)
    return stem.capitalize()
