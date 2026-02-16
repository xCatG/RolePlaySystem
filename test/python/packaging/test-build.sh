#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Package Build Testing Script ===${NC}"
echo "Testing the role_play_system package build process..."
echo ""

# Change to the script directory and find project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
PYTHON_SRC_DIR="$PROJECT_ROOT/src/python"

# Change to python source directory for build operations
cd "$PYTHON_SRC_DIR"

# Activate virtual environment if it exists  
VENV_PATH="$PROJECT_ROOT/venv"
if [ -d "$VENV_PATH" ]; then
    echo "Activating virtual environment..."
    source "$VENV_PATH/bin/activate"
    echo -e "${GREEN}✅ Virtual environment activated${NC}"
else
    echo -e "${YELLOW}⚠️  No virtual environment found at $VENV_PATH${NC}"
    echo "Make sure required packages (build, setuptools, wheel) are installed globally"
fi
echo ""

# Test 1: Clean build
echo -e "${YELLOW}1. Testing clean build...${NC}"
if [ -d "role_play/dist" ]; then
    echo "Cleaning existing build artifacts..."
    rm -rf role_play/dist role_play/build role_play/*.egg-info
fi

./build.sh

# Test 2: Verify build artifacts
echo -e "${YELLOW}2. Verifying build artifacts...${NC}"
if [ ! -d "role_play/dist" ]; then
    echo -e "${RED}❌ FAIL: dist directory not created${NC}"
    exit 1
fi

WHEEL_FILE=$(find role_play/dist -name "*.whl" -type f)
TARBALL_FILE=$(find role_play/dist -name "*.tar.gz" -type f)

if [ -z "$WHEEL_FILE" ]; then
    echo -e "${RED}❌ FAIL: .whl file not found${NC}"
    exit 1
else
    echo -e "${GREEN}✅ PASS: Wheel file created: $(basename "$WHEEL_FILE")${NC}"
fi

if [ -z "$TARBALL_FILE" ]; then
    echo -e "${RED}❌ FAIL: .tar.gz file not found${NC}"
    exit 1
else
    echo -e "${GREEN}✅ PASS: Tarball created: $(basename "$TARBALL_FILE")${NC}"
fi

# Test 3: Validate package metadata
echo -e "${YELLOW}3. Validating package metadata...${NC}"
if command -v twine >/dev/null 2>&1; then
    echo "Running twine check..."
    if twine check role_play/dist/*; then
        echo -e "${GREEN}✅ PASS: Package metadata is valid${NC}"
    else
        echo -e "${RED}❌ FAIL: Package metadata validation failed${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  SKIP: twine not installed, skipping metadata validation${NC}"
    echo "Install with: pip install twine"
fi

# Test 4: Check package contents
echo -e "${YELLOW}4. Checking package contents...${NC}"
echo "Wheel file contents:"
if command -v unzip >/dev/null 2>&1; then
    unzip -l "$WHEEL_FILE" | grep -E '\.(py|md|txt|LICENSE)$' || true
else
    echo "unzip not available, skipping wheel content check"
fi

echo ""
echo "Tarball contents:"
if command -v tar >/dev/null 2>&1; then
    tar -tzf "$TARBALL_FILE" | grep -E '\.(py|md|txt|LICENSE)$' | head -20 || true
else
    echo "tar not available, skipping tarball content check"
fi

# Test 5: File sizes
echo -e "${YELLOW}5. Checking file sizes...${NC}"
WHEEL_SIZE=$(stat -f%z "$WHEEL_FILE" 2>/dev/null || stat -c%s "$WHEEL_FILE" 2>/dev/null || echo "unknown")
TARBALL_SIZE=$(stat -f%z "$TARBALL_FILE" 2>/dev/null || stat -c%s "$TARBALL_FILE" 2>/dev/null || echo "unknown")

echo "Wheel size: $WHEEL_SIZE bytes"
echo "Tarball size: $TARBALL_SIZE bytes"

# Check for reasonable sizes (not empty, not suspiciously large)
if [ "$WHEEL_SIZE" != "unknown" ] && [ "$WHEEL_SIZE" -lt 1000 ]; then
    echo -e "${RED}❌ WARNING: Wheel file seems very small${NC}"
elif [ "$WHEEL_SIZE" != "unknown" ] && [ "$WHEEL_SIZE" -gt 50000000 ]; then
    echo -e "${RED}❌ WARNING: Wheel file seems very large${NC}"
else
    echo -e "${GREEN}✅ PASS: File sizes look reasonable${NC}"
fi

# Test 6: Check required files are included
echo -e "${YELLOW}6. Checking required files...${NC}"
REQUIRED_FILES=("LICENSE" "README.md" "pyproject.toml")
for file in "${REQUIRED_FILES[@]}"; do
    if tar -tzf "$TARBALL_FILE" | grep -q "$file$"; then
        echo -e "${GREEN}✅ PASS: $file included in package${NC}"
    else
        echo -e "${RED}❌ FAIL: $file missing from package${NC}"
    fi
done

echo ""
echo -e "${BLUE}=== Build Test Summary ===${NC}"
echo -e "${GREEN}Build test completed successfully!${NC}"
echo ""
echo "Next steps:"
echo "1. Run installation test: ./test/python/packaging/test-install.sh"
echo "2. Test GCP upload: ./test/python/packaging/test-gcp-upload.sh"
echo "3. Create version tag when ready: git tag v0.1.0 && git push origin v0.1.0"
echo ""