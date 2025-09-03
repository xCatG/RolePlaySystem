#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== GCP Artifact Registry Testing Script ===${NC}"
echo "Testing GCP Artifact Registry upload and configuration..."
echo ""

# Configuration variables (edit these)
DEFAULT_PROJECT_ID="your-project-id"
DEFAULT_REGION="us-central1"
DEFAULT_REPO="python-packages"
TEST_REPO="python-test"

# Change to the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment if it exists (for twine and auth tools)
VENV_PATH="../../venv"
if [ -d "$VENV_PATH" ]; then
    echo "Activating virtual environment..."
    source "$VENV_PATH/bin/activate"
    echo -e "${GREEN}✅ Virtual environment activated${NC}"
else
    echo -e "${YELLOW}⚠️  No virtual environment found at $VENV_PATH${NC}"
    echo "Make sure twine is installed globally"
fi
echo ""

# Function to prompt for input with default
prompt_with_default() {
    local prompt="$1"
    local default="$2"
    local response
    
    read -p "$prompt [$default]: " response
    echo "${response:-$default}"
}

# Get configuration
echo -e "${YELLOW}Please enter your GCP configuration:${NC}"
PROJECT_ID=$(prompt_with_default "GCP Project ID" "$DEFAULT_PROJECT_ID")
REGION=$(prompt_with_default "GCP Region" "$DEFAULT_REGION")
REPO_NAME=$(prompt_with_default "Repository name for testing" "$TEST_REPO")

echo ""
echo "Using configuration:"
echo "  Project ID: $PROJECT_ID"
echo "  Region: $REGION"
echo "  Test Repository: $REPO_NAME"
echo ""

# Test 1: Check GCP CLI installation
echo -e "${YELLOW}1. Checking GCP CLI installation...${NC}"
if command -v gcloud >/dev/null 2>&1; then
    echo -e "${GREEN}✅ PASS: gcloud CLI is installed${NC}"
    gcloud version | head -1
else
    echo -e "${RED}❌ FAIL: gcloud CLI not found${NC}"
    echo "Please install: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Test 2: Check authentication
echo -e "${YELLOW}2. Checking GCP authentication...${NC}"
if gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1 >/dev/null; then
    ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1)
    echo -e "${GREEN}✅ PASS: Authenticated as $ACTIVE_ACCOUNT${NC}"
else
    echo -e "${RED}❌ FAIL: Not authenticated with GCP${NC}"
    echo "Run: gcloud auth login"
    exit 1
fi

# Test 3: Check project access
echo -e "${YELLOW}3. Checking project access...${NC}"
if gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1; then
    echo -e "${GREEN}✅ PASS: Can access project $PROJECT_ID${NC}"
else
    echo -e "${RED}❌ FAIL: Cannot access project $PROJECT_ID${NC}"
    echo "Check project ID and permissions"
    exit 1
fi

# Test 4: Check Artifact Registry API
echo -e "${YELLOW}4. Checking Artifact Registry API...${NC}"
if gcloud services list --enabled --filter="name:artifactregistry.googleapis.com" --format="value(name)" | grep -q artifactregistry; then
    echo -e "${GREEN}✅ PASS: Artifact Registry API is enabled${NC}"
else
    echo -e "${RED}❌ FAIL: Artifact Registry API is not enabled${NC}"
    echo "Enable it with: gcloud services enable artifactregistry.googleapis.com --project=$PROJECT_ID"
    exit 1
fi

# Test 5: Check/Create test repository
echo -e "${YELLOW}5. Checking test repository...${NC}"
if gcloud artifacts repositories describe "$REPO_NAME" --location="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo -e "${GREEN}✅ PASS: Test repository $REPO_NAME already exists${NC}"
else
    echo -e "${YELLOW}Test repository doesn't exist. Creating it...${NC}"
    if gcloud artifacts repositories create "$REPO_NAME" \
        --repository-format=python \
        --location="$REGION" \
        --project="$PROJECT_ID"; then
        echo -e "${GREEN}✅ PASS: Test repository created successfully${NC}"
    else
        echo -e "${RED}❌ FAIL: Could not create test repository${NC}"
        exit 1
    fi
fi

# Test 6: Check build artifacts
echo -e "${YELLOW}6. Checking build artifacts...${NC}"
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

echo -e "${GREEN}✅ PASS: Build artifacts found${NC}"
echo "  Wheel: $(basename "$WHEEL_FILE")"
echo "  Tarball: $(basename "$TARBALL_FILE")"

# Test 7: Install and configure twine
echo -e "${YELLOW}7. Setting up twine for Artifact Registry...${NC}"
if ! pip list | grep -q twine; then
    echo "Installing twine..."
    pip install twine
fi

if ! pip list | grep -q keyrings.google-artifactregistry-auth; then
    echo "Installing Google Artifact Registry auth..."
    pip install keyrings.google-artifactregistry-auth
fi

echo -e "${GREEN}✅ PASS: Twine and auth tools installed${NC}"

# Test 8: Test twine check
echo -e "${YELLOW}8. Running twine check...${NC}"
cd role_play
if twine check dist/*; then
    echo -e "${GREEN}✅ PASS: Package validation successful${NC}"
else
    echo -e "${RED}❌ FAIL: Package validation failed${NC}"
    cd "$SCRIPT_DIR"
    exit 1
fi
cd "$SCRIPT_DIR"

# Test 9: Test upload (dry run)
echo -e "${YELLOW}9. Testing upload configuration...${NC}"
REPO_URL="https://$REGION-python.pkg.dev/$PROJECT_ID/$REPO_NAME/"

echo "Repository URL: $REPO_URL"
echo ""

# Ask for confirmation before actual upload
echo -e "${YELLOW}Do you want to perform an actual test upload? (y/N):${NC}"
read -r CONFIRM

if [[ $CONFIRM =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}10. Performing test upload...${NC}"
    cd role_play
    
    if twine upload --repository-url "$REPO_URL" dist/* --verbose; then
        echo -e "${GREEN}✅ PASS: Test upload successful!${NC}"
        
        # Test 11: Try to install from uploaded package
        echo -e "${YELLOW}11. Testing installation from Artifact Registry...${NC}"
        
        # Create temp environment for test
        TEMP_ENV="temp_test_env"
        python3 -m venv "$TEMP_ENV"
        source "$TEMP_ENV/bin/activate"
        
        # Configure pip for Artifact Registry
        PACKAGE_URL="https://$REGION-python.pkg.dev/$PROJECT_ID/$REPO_NAME/simple/"
        
        if pip install role-play-system --extra-index-url "$PACKAGE_URL" --no-cache-dir; then
            echo -e "${GREEN}✅ PASS: Installation from Artifact Registry successful!${NC}"
            
            # Quick import test
            python3 -c "import chat; print('Package works!')" 2>/dev/null && \
            echo -e "${GREEN}✅ PASS: Package import successful!${NC}" || \
            echo -e "${YELLOW}⚠️  WARNING: Package import had issues${NC}"
            
        else
            echo -e "${RED}❌ FAIL: Could not install from Artifact Registry${NC}"
        fi
        
        deactivate
        rm -rf "$TEMP_ENV"
        
    else
        echo -e "${RED}❌ FAIL: Test upload failed${NC}"
    fi
    
    cd "$SCRIPT_DIR"
else
    echo -e "${YELLOW}Skipping actual upload test${NC}"
fi

# Test 12: Show cleanup commands
echo ""
echo -e "${YELLOW}12. Cleanup information...${NC}"
echo "To clean up the test repository later, run:"
echo "  gcloud artifacts repositories delete $REPO_NAME --location=$REGION --project=$PROJECT_ID"
echo ""
echo "To delete uploaded packages, use the GCP Console:"
echo "  https://console.cloud.google.com/artifacts/browse/$PROJECT_ID/$REGION/$REPO_NAME"

echo ""
echo -e "${BLUE}=== GCP Upload Test Summary ===${NC}"
echo -e "${GREEN}GCP configuration test completed!${NC}"
echo ""
echo "Your setup is ready for:"
echo "1. Automated GitHub Actions publishing"
echo "2. Manual package uploads"
echo "3. Package installation from private registry"
echo ""
echo "Next steps:"
echo "1. Configure GitHub repository secrets:"
echo "   - GCP_PROJECT_ID: $PROJECT_ID"
echo "   - GCP_REGION: $REGION"
echo "   - GCP_ARTIFACT_REGISTRY_REPO: $DEFAULT_REPO"
echo "   - GCP_SA_KEY: <service account JSON key>"
echo ""
echo "2. Create production repository if needed:"
echo "   gcloud artifacts repositories create $DEFAULT_REPO --repository-format=python --location=$REGION --project=$PROJECT_ID"
echo ""
echo "3. Create version tag for release:"
echo "   git tag v0.1.0 && git push origin v0.1.0"
echo ""