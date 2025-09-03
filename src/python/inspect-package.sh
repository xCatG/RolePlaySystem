#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Package Content Inspection Script ===${NC}"
echo "Detailed inspection of the role_play_system package contents..."
echo ""

# Change to the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Note: This script only uses system tools (unzip, tar) and doesn't need venv activation

# Check if build artifacts exist
if [ ! -d "role_play/dist" ]; then
    echo -e "${RED}❌ FAIL: No dist directory found. Run ./build.sh first.${NC}"
    exit 1
fi

WHEEL_FILE=$(find role_play/dist -name "*.whl" -type f | head -1)
TARBALL_FILE=$(find role_play/dist -name "*.tar.gz" -type f | head -1)

if [ -z "$WHEEL_FILE" ] || [ -z "$TARBALL_FILE" ]; then
    echo -e "${RED}❌ FAIL: Build artifacts not found. Run ./build.sh first.${NC}"
    exit 1
fi

echo "Inspecting files:"
echo "  Wheel: $(basename "$WHEEL_FILE")"
echo "  Tarball: $(basename "$TARBALL_FILE")"
echo ""

# Function to check if file exists in archive
check_file_in_wheel() {
    local file_pattern="$1"
    local description="$2"
    
    if unzip -l "$WHEEL_FILE" 2>/dev/null | grep -q "$file_pattern"; then
        echo -e "${GREEN}✅ FOUND: $description${NC}"
        return 0
    else
        echo -e "${RED}❌ MISSING: $description${NC}"
        return 1
    fi
}

check_file_in_tarball() {
    local file_pattern="$1"
    local description="$2"
    
    if tar -tzf "$TARBALL_FILE" 2>/dev/null | grep -q "$file_pattern"; then
        echo -e "${GREEN}✅ FOUND: $description${NC}"
        return 0
    else
        echo -e "${RED}❌ MISSING: $description${NC}"
        return 1
    fi
}

# Test 1: Check for core Python modules
echo -e "${YELLOW}1. Checking core Python modules...${NC}"
MODULES=("chat" "common" "server" "voice" "evaluation" "dev_agents" "scripter")
for module in "${MODULES[@]}"; do
    check_file_in_wheel "$module/" "Module: $module"
done

# Test 2: Check for essential files
echo -e "${YELLOW}2. Checking essential files...${NC}"
check_file_in_tarball "LICENSE" "License file"
check_file_in_tarball "README.md" "README file"
check_file_in_tarball "pyproject.toml" "pyproject.toml"

# Test 3: Check for package metadata files
echo -e "${YELLOW}3. Checking package metadata...${NC}"
check_file_in_wheel "METADATA" "Package metadata"
check_file_in_wheel "WHEEL" "Wheel metadata"

# Test 4: Detailed content listing
echo -e "${YELLOW}4. Detailed content listing...${NC}"
echo ""
echo -e "${BLUE}--- Wheel Contents ---${NC}"
unzip -l "$WHEEL_FILE" | head -50

echo ""
echo -e "${BLUE}--- Tarball Contents (first 30 files) ---${NC}"
tar -tzf "$TARBALL_FILE" | head -30

# Test 5: Check file sizes and structure
echo ""
echo -e "${YELLOW}5. Analyzing package structure...${NC}"

# Count Python files
PY_FILES=$(unzip -l "$WHEEL_FILE" | grep -c '\.py$' || echo "0")
echo "Python files in wheel: $PY_FILES"

# Check for __init__.py files
INIT_FILES=$(unzip -l "$WHEEL_FILE" | grep -c '__init__.py$' || echo "0")
echo "Module __init__.py files: $INIT_FILES"

# Check for any suspicious files
echo ""
echo -e "${YELLOW}6. Checking for unwanted files...${NC}"

SUSPICIOUS_PATTERNS=("__pycache__" "\.pyc$" "\.pyo$" "\.git" "\.DS_Store" "\.pytest_cache")
FOUND_SUSPICIOUS=false

for pattern in "${SUSPICIOUS_PATTERNS[@]}"; do
    if unzip -l "$WHEEL_FILE" | grep -q "$pattern"; then
        echo -e "${RED}❌ FOUND UNWANTED: Files matching $pattern${NC}"
        unzip -l "$WHEEL_FILE" | grep "$pattern"
        FOUND_SUSPICIOUS=true
    fi
done

if [ "$FOUND_SUSPICIOUS" = false ]; then
    echo -e "${GREEN}✅ CLEAN: No unwanted files found${NC}"
fi

# Test 7: Check dependencies in metadata
echo ""
echo -e "${YELLOW}7. Checking dependency information...${NC}"

# Extract and show METADATA file from wheel
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"
unzip -q "$WHEEL_FILE" "*.dist-info/METADATA" 2>/dev/null || true

METADATA_FILE=$(find . -name "METADATA" -type f | head -1)
if [ -n "$METADATA_FILE" ]; then
    echo "Dependencies listed in METADATA:"
    grep -E "^Requires-Dist:" "$METADATA_FILE" || echo "No dependencies found"
    echo ""
    echo "Package info:"
    head -20 "$METADATA_FILE"
else
    echo -e "${RED}❌ METADATA file not found${NC}"
fi

cd "$SCRIPT_DIR"
rm -rf "$TEMP_DIR"

# Test 8: Compare wheel and tarball contents
echo ""
echo -e "${YELLOW}8. Comparing wheel and tarball...${NC}"

WHEEL_FILE_COUNT=$(unzip -l "$WHEEL_FILE" | grep -c '\.py$' || echo "0")
TARBALL_FILE_COUNT=$(tar -tzf "$TARBALL_FILE" | grep -c '\.py$' || echo "0")

echo "Python files in wheel: $WHEEL_FILE_COUNT"
echo "Python files in tarball: $TARBALL_FILE_COUNT"

if [ "$WHEEL_FILE_COUNT" -eq "$TARBALL_FILE_COUNT" ]; then
    echo -e "${GREEN}✅ CONSISTENT: Same number of Python files in both archives${NC}"
else
    echo -e "${YELLOW}⚠️  WARNING: Different number of Python files${NC}"
fi

echo ""
echo -e "${BLUE}=== Package Inspection Summary ===${NC}"
echo -e "${GREEN}Package inspection completed!${NC}"
echo ""
echo "Files inspected:"
echo "  - $(basename "$WHEEL_FILE") ($(stat -f%z "$WHEEL_FILE" 2>/dev/null || stat -c%s "$WHEEL_FILE") bytes)"
echo "  - $(basename "$TARBALL_FILE") ($(stat -f%z "$TARBALL_FILE" 2>/dev/null || stat -c%s "$TARBALL_FILE") bytes)"
echo ""
echo "Use this information to verify your package contains all expected files"
echo "and doesn't include any unwanted development artifacts."
echo ""