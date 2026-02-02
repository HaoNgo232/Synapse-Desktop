#!/bin/bash
# Build AppImage for Synapse Desktop
# Usage: ./build-appimage.sh
#
# Requirements:
# - Python 3.12+
# - pip packages installed in .venv
# - appimagetool (auto-downloaded if not present)

set -e

APP_NAME="Synapse-Desktop"
APP_VERSION="1.0.0"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
APPDIR="$BUILD_DIR/$APP_NAME.AppDir"

echo "========================================"
echo "Building $APP_NAME v$APP_VERSION AppImage"
echo "========================================"

# Cleanup previous build
rm -rf "$BUILD_DIR"
mkdir -p "$APPDIR"

# Create AppDir structure
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

echo "[1/6] Installing PyInstaller..."
source "$SCRIPT_DIR/.venv/bin/activate"
pip install pyinstaller --quiet

echo "[2/6] Building with PyInstaller..."
pyinstaller \
    --name "$APP_NAME" \
    --onedir \
    --windowed \
    --noconfirm \
    --clean \
    --add-data "$SCRIPT_DIR/assets:assets" \
    --hidden-import flet \
    --hidden-import flet.core \
    --hidden-import flet_desktop \
    --hidden-import tiktoken_ext \
    --hidden-import tiktoken_ext.openai_public \
    --collect-all flet \
    --collect-all flet_desktop \
    --collect-all tiktoken_ext \
    --distpath "$BUILD_DIR/dist" \
    --workpath "$BUILD_DIR/work" \
    --specpath "$BUILD_DIR" \
    main.py

echo "[3/6] Copying files to AppDir..."
cp -r "$BUILD_DIR/dist/$APP_NAME"/* "$APPDIR/usr/bin/"

# Copy icon
if [ -f "$SCRIPT_DIR/assets/icon.png" ]; then
    cp "$SCRIPT_DIR/assets/icon.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/$APP_NAME.png"
    cp "$SCRIPT_DIR/assets/icon.png" "$APPDIR/$APP_NAME.png"
else
    echo "Warning: assets/icon.png not found, using placeholder"
    # Create a simple placeholder icon (1x1 pixel)
    echo -n "" > "$APPDIR/$APP_NAME.png"
fi

echo "[4/6] Creating desktop entry..."
cat > "$APPDIR/$APP_NAME.desktop" << EOF
[Desktop Entry]
Type=Application
Name=Synapse Desktop
Comment=Copy Context and Apply OPX for AI-assisted coding
Exec=$APP_NAME
Icon=$APP_NAME
Categories=Development;IDE;
Terminal=false
EOF

cp "$APPDIR/$APP_NAME.desktop" "$APPDIR/usr/share/applications/"

echo "[5/6] Creating AppRun..."
cat > "$APPDIR/AppRun" << 'EOF'
#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/lib:${LD_LIBRARY_PATH}"
exec "${HERE}/usr/bin/Synapse-Desktop" "$@"
EOF
chmod +x "$APPDIR/AppRun"

echo "[6/6] Building AppImage..."
# Download appimagetool if not present
APPIMAGETOOL="$BUILD_DIR/appimagetool-x86_64.AppImage"
if [ ! -f "$APPIMAGETOOL" ]; then
    echo "Downloading appimagetool..."
    wget -q "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" \
        -O "$APPIMAGETOOL"
    chmod +x "$APPIMAGETOOL"
fi

# Build AppImage
ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "$BUILD_DIR/$APP_NAME-$APP_VERSION-x86_64.AppImage"

echo ""
echo "========================================"
echo "Build complete!"
echo "AppImage: $BUILD_DIR/$APP_NAME-$APP_VERSION-x86_64.AppImage"
echo "========================================"
