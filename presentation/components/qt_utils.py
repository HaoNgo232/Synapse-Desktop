"""
Utility functions for PySide6 components.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer


def create_colored_icon(svg_path: str, color: str) -> QIcon:
    """Create a colored icon from SVG by replacing fill/stroke colors."""
    try:
        # Read SVG content
        with open(svg_path, "r", encoding="utf-8") as f:
            svg_content = f.read()

        # Replace colors (simple approach - replace common attributes)
        # Handle 'currentColor', black, and hex variants
        lower_content = svg_content.lower()

        # If it uses currentColor, replace that first
        svg_content = svg_content.replace("currentColor", color)
        svg_content = svg_content.replace('stroke="black"', f'stroke="{color}"')
        svg_content = svg_content.replace('fill="black"', f'fill="{color}"')
        svg_content = svg_content.replace('stroke="#000000"', f'stroke="{color}"')
        svg_content = svg_content.replace('fill="#000000"', f'fill="{color}"')

        # If it's a stroke-only SVG and has no explicit stroke but has paths, add stroke
        if "stroke=" not in lower_content and "<path" in lower_content:
            svg_content = svg_content.replace("<path", f'<path stroke="{color}"')

        # Render to pixmap
        renderer = QSvgRenderer(svg_content.encode("utf-8"))
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()

        return QIcon(pixmap)
    except Exception:
        # Fallback to original icon if anything fails
        return QIcon(svg_path)
