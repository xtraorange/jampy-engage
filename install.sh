#!/bin/bash
# One-line installer for jampy-engage
# Usage:
#   On macOS/Linux:
#   curl -fsSL https://raw.githubusercontent.com/[USERNAME]/jampy-engage/main/install.sh | bash
#
#   On Windows (PowerShell):
#   irm https://raw.githubusercontent.com/[USERNAME]/jampy-engage/main/install.ps1 | iex

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}    jampy-engage Installer${NC}"
echo -e "${GREEN}========================================${NC}"

# Check for Python
echo -e "${YELLOW}Checking for Python installation...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is required but not installed.${NC}"
    echo "Please install Python 3 from https://www.python.org/"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✓ Python ${PYTHON_VERSION} found${NC}"

# Get target directory
if [ -z "$1" ]; then
    TARGET_DIR="$HOME/jampy-engage"
else
    TARGET_DIR="$1"
fi

echo -e "${YELLOW}Installing to: $TARGET_DIR${NC}"

# Clone repo
if [ ! -d "$TARGET_DIR" ]; then
    echo -e "${YELLOW}Cloning repository...${NC}"
    git clone https://github.com/[USERNAME]/jampy-engage.git "$TARGET_DIR"
else
    echo -e "${YELLOW}Directory exists, pulling latest changes...${NC}"
    cd "$TARGET_DIR"
    git pull
fi

cd "$TARGET_DIR"

# Create virtual environment
echo -e "${YELLOW}Creating virtual environment...${NC}"
python3 -m venv .venv

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source .venv/bin/activate

# Install requirements
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}    Installation Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "To start the application:"
echo -e "  ${YELLOW}cd $TARGET_DIR${NC}"
echo -e "  ${YELLOW}python run_reports.py${NC}"
echo ""
echo -e "The browser will automatically open to: ${YELLOW}http://localhost:5000${NC}"
echo ""
