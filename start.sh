#!/bin/bash

# Startup script for Synapse Desktop
# Automatically checks and creates virtual environment if needed

VENV_DIR=".venv"
REQUIREMENTS_FILE="requirements.txt"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Synapse Desktop Startup Script ===${NC}\n"

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}Virtual environment does not exist at: $VENV_DIR${NC}"
    read -p "Do you want to create a virtual environment? (y/n): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}Creating virtual environment...${NC}"
        python3 -m venv "$VENV_DIR"
        
        if [ $? -ne 0 ]; then
            echo -e "${RED}Error: Could not create virtual environment!${NC}"
            echo -e "${YELLOW}Please check if python3-venv is installed.${NC}"
            echo -e "${YELLOW}Run: sudo apt install python3-venv${NC}"
            exit 1
        fi
        
        echo -e "${GREEN}Virtual environment created successfully!${NC}\n"
    else
        echo -e "${RED}Cannot continue without a virtual environment.${NC}"
        exit 1
    fi
fi

# Activate virtual environment
echo -e "${GREEN}Activating virtual environment...${NC}"
source "$VENV_DIR/bin/activate"

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Could not activate virtual environment!${NC}"
    exit 1
fi

# Check if successfully entered virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${RED}Error: Virtual environment is not activated!${NC}"
    echo -e "${YELLOW}VIRTUAL_ENV environment variable is not set.${NC}"
    echo -e "${RED}Cannot continue. Please check your configuration.${NC}"
    exit 1
fi

echo -e "${GREEN}Virtual environment activated: $VIRTUAL_ENV${NC}\n"

# Check requirements.txt file
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo -e "${YELLOW}Warning: $REQUIREMENTS_FILE file not found${NC}"
    echo -e "${YELLOW}Skipping dependency installation.${NC}\n"
else
    # Install dependencies
    echo -e "${GREEN}Installing dependencies from $REQUIREMENTS_FILE...${NC}"
    pip install -r "$REQUIREMENTS_FILE"
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: Failed to install dependencies!${NC}"
        echo -e "${YELLOW}Please check $REQUIREMENTS_FILE and your internet connection.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}Dependencies installed successfully!${NC}\n"
fi

# Check main_window.py (PySide6 entry point)
if [ ! -f "main_window.py" ]; then
    echo -e "${RED}Error: main_window.py not found!${NC}"
    exit 1
fi

# Start application
echo -e "${GREEN}Starting application (PySide6)...${NC}\n"
python3 main_window.py

# Save exit code
APP_EXIT_CODE=$?

# Deactivate virtual environment on exit
deactivate 2>/dev/null

if [ $APP_EXIT_CODE -ne 0 ]; then
    echo -e "\n${RED}Application exited with error code: $APP_EXIT_CODE${NC}"
    exit $APP_EXIT_CODE
fi

echo -e "\n${GREEN}Application exited successfully.${NC}"