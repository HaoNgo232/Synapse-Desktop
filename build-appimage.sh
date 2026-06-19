#!/bin/bash
# Build AppImage for Synapse Desktop
# Usage: ./build-appimage.sh
#
# Requirements:
# - Python 3.12+
# - pip packages installed in .venv
# - appimagetool (auto-downloaded if not present)

set -e

APP_NAME="Synapse"
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

echo "[1/6] Activating virtual environment..."
VENV_DIR="$SCRIPT_DIR/.venv"
if [ -d "$VENV_DIR/Scripts" ] || ( [ -f "$VENV_DIR/pyvenv.cfg" ] && grep -q "python.exe" "$VENV_DIR/pyvenv.cfg" ); then
    VENV_DIR="$SCRIPT_DIR/.venv-linux"
fi

if [ ! -d "$VENV_DIR" ] || [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "Creating Linux virtual environment at $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    echo "Installing requirements..."
    python3 -m pip install --upgrade pip
    pip install -r "$SCRIPT_DIR/requirements.txt"
else
    source "$VENV_DIR/bin/activate"
fi

echo "Installing PyInstaller..."
pip install pyinstaller --quiet

echo "Fetching material icons if missing..."
python3 scripts/fetch_material_icons.py

echo "[2/6] Building with PyInstaller..."
pyinstaller \
    --name "$APP_NAME" \
    --onedir \
    --windowed \
    --noconfirm \
    --clean \
    --add-data "$SCRIPT_DIR/assets:assets" \
    --add-data "$SCRIPT_DIR/domain/prompt/templates:domain/prompt/templates" \
    --add-data "$SCRIPT_DIR/domain/codemap/queries:domain/codemap/queries" \
    --hidden-import tiktoken_ext \
    --hidden-import tiktoken_ext.openai_public \
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
cat > "$APPDIR/AppRun" << EOF
#!/bin/bash
SELF=\$(readlink -f "\$0")
HERE=\${SELF%/*}
export PATH="\${HERE}/usr/bin:\${PATH}"
export LD_LIBRARY_PATH="\${HERE}/usr/lib:\${LD_LIBRARY_PATH}"
exec "\${HERE}/usr/bin/${APP_NAME}" "\$@"
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
echo "AppImage created: $BUILD_DIR/$APP_NAME-$APP_VERSION-x86_64.AppImage"
echo "========================================"

# Auto move to Desktop
DESKTOP_DIR="$HOME/Desktop"

# Detect WSL to move to Windows Desktop
if grep -qE "(Microsoft|WSL)" /proc/version 2>/dev/null; then
    # Method 1: Try interop with cmd.exe
    WIN_USERPROFILE=$(cmd.exe /c "echo %USERPROFILE%" 2>/dev/null | tr -d '\r')
    if [ -n "$WIN_USERPROFILE" ]; then
        WSL_DESKTOP=$(wslpath "$WIN_USERPROFILE/Desktop" 2>/dev/null)
        if [ -d "$WSL_DESKTOP" ]; then
            DESKTOP_DIR="$WSL_DESKTOP"
        fi
    fi

    # Method 2: Case-insensitive match under /mnt/c/Users if Method 1 failed
    if [ "$DESKTOP_DIR" = "$HOME/Desktop" ] || [ ! -d "$DESKTOP_DIR" ]; then
        WSL_USER=$(whoami)
        for d in /mnt/c/Users/*; do
            if [ -d "$d/Desktop" ] && [ "$(echo "$(basename "$d")" | tr '[:upper:]' '[:lower:]')" = "$(echo "$WSL_USER" | tr '[:upper:]' '[:lower:]')" ]; then
                DESKTOP_DIR="$d/Desktop"
                break
            fi
        done
    fi

    # Method 3: Find any user folder on C: drive that has a Desktop (excluding system profiles)
    if [ "$DESKTOP_DIR" = "$HOME/Desktop" ] || [ ! -d "$DESKTOP_DIR" ]; then
        for d in /mnt/c/Users/*; do
            bname=$(basename "$d")
            if [ "$bname" != "Public" ] && [ "$bname" != "All Users" ] && [ "$bname" != "Default" ] && [ "$bname" != "Default User" ] && [ -d "$d/Desktop" ]; then
                DESKTOP_DIR="$d/Desktop"
                break
            fi
        done
    fi
fi

OUTPUT_FILE="$BUILD_DIR/$APP_NAME-$APP_VERSION-x86_64.AppImage"
DESKTOP_DEST="$DESKTOP_DIR/$APP_NAME.AppImage"

if [ -f "$OUTPUT_FILE" ]; then
    # Ensure destination directory exists
    mkdir -p "$DESKTOP_DIR"
    echo "Moving AppImage to Desktop..."
    if mv -f "$OUTPUT_FILE" "$DESKTOP_DEST" 2>/dev/null; then
        chmod +x "$DESKTOP_DEST"
        echo "Successfully moved to: $DESKTOP_DEST"
    else
        # Fallback to copy + remove (useful for cross-device mount links in WSL)
        if cp "$OUTPUT_FILE" "$DESKTOP_DEST" 2>/dev/null; then
            rm -f "$OUTPUT_FILE"
            chmod +x "$DESKTOP_DEST"
            echo "Successfully moved to: $DESKTOP_DEST"
        else
            echo "Warning: Could not move AppImage to Desktop. File remains at: $OUTPUT_FILE"
        fi
    fi
else
    echo "Warning: Build succeeded but AppImage file not found at $OUTPUT_FILE"
fi
