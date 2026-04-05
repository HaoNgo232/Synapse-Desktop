#!/bin/bash
# Script để chạy CodeMaps demo test trong venv

cd "$(dirname "$0")/.."

# Activate venv (same as start.sh)
VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Error: Virtual environment not found at $VENV_DIR"
    exit 1
fi

source "$VENV_DIR/bin/activate"

# Run demo test
echo "Running CodeMaps Integration Demo..."
python demo_codemaps_integration.py
