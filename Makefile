# Makefile for Role Play System (RPS)

# --- Configuration ---
# SERVICE_NAME: Used for naming resources. Override for different services.
SERVICE_NAME ?= rps
# DEFAULT_ENV: Default environment if ENV is not set.
DEFAULT_ENV ?= dev
# ENV: Current operational environment (dev, beta, prod). Set via command line: make deploy ENV=prod
ENV ?= $(DEFAULT_ENV)

# GCP Region for deployments
GCP_REGION ?= us-west1

# Docker Image Configuration
# ARTIFACT_REGISTRY_REPO: Name of your Artifact Registry repository.
ARTIFACT_REGISTRY_REPO ?= $(SERVICE_NAME)-images
# IMAGE_NAME_BASE: Base name for the Docker image in Artifact Registry.
IMAGE_NAME_BASE = $(GCP_REGION)-docker.pkg.dev/$(TARGET_GCP_PROJECT_ID)/$(ARTIFACT_REGISTRY_REPO)/$(SERVICE_NAME)-api

# Git version for tagging Docker images. Uses current git tag or short commit SHA.
GIT_VERSION ?= $(shell git describe --tags --always --dirty --match "v*" 2>/dev/null || echo "dev")
# IMAGE_TAG: Tag for the Docker image (e.g., git version or 'latest').
IMAGE_TAG ?= $(GIT_VERSION)

# Frontend source directory
FRONTEND_DIR = src/ts/role_play/ui
# Backend source directory (Python)
BACKEND_DIR = src/python

# --- Environment-Specific GCP Project IDs & Configs ---
# These MUST be set in your environment (e.g., export GCP_PROJECT_ID_PROD="your-id")
# or in an uncommitted .env.mk file (see .PHONY: load-env-mk)
# Fallback to a placeholder to avoid errors if not set, but deployments will fail.
GCP_PROJECT_ID_PROD ?= placeholder-prod-project-id
GCP_PROJECT_ID_BETA ?= placeholder-beta-project-id
GCP_PROJECT_ID_DEV ?= placeholder-dev-project-id

TARGET_GCP_PROJECT_ID = ""
CLOUD_RUN_SERVICE_NAME = ""
GCS_BUCKET_APP_DATA = ""
GCS_PREFIX_APP_DATA = ""
GCS_BUCKET_LOG_EXPORTS = "" # Optional
CONFIG_FILE_PATH_IN_CONTAINER = ""
CLOUD_RUN_MIN_INSTANCES = 0
CLOUD_RUN_MAX_INSTANCES = 10
LOG_LEVEL_CONFIG = "INFO"
CORS_ORIGINS_CONFIG = "http://localhost:3000,http://localhost:5173" # Default for local dev
SERVICE_ACCOUNT_EMAIL = "" # Expected to be set per environment
API_BASE_URL_FOR_APP = "/api" # Default API prefix for the application

ifeq ($(ENV),prod)
	TARGET_GCP_PROJECT_ID = $(GCP_PROJECT_ID_PROD)
	CLOUD_RUN_SERVICE_NAME = $(SERVICE_NAME)-api-prod
	GCS_BUCKET_APP_DATA = $(SERVICE_NAME)-app-data-prod
	GCS_PREFIX_APP_DATA = prod/
	GCS_BUCKET_LOG_EXPORTS = $(SERVICE_NAME)-log-exports-prod
	CONFIG_FILE_PATH_IN_CONTAINER = /app/config/prod.yaml
	CLOUD_RUN_MIN_INSTANCES = 1
	LOG_LEVEL_CONFIG = "WARNING"
	CORS_ORIGINS_CONFIG = "https://rps.cattail-sw.com"
	SERVICE_ACCOUNT_EMAIL = sa-$(SERVICE_NAME)@$(GCP_PROJECT_ID_PROD).iam.gserviceaccount.com
else ifeq ($(ENV),beta)
	TARGET_GCP_PROJECT_ID = $(GCP_PROJECT_ID_BETA)
	CLOUD_RUN_SERVICE_NAME = $(SERVICE_NAME)-api-beta
	GCS_BUCKET_APP_DATA = $(SERVICE_NAME)-app-data-beta
	GCS_PREFIX_APP_DATA = beta/
	GCS_BUCKET_LOG_EXPORTS = $(SERVICE_NAME)-log-exports-beta
	CONFIG_FILE_PATH_IN_CONTAINER = /app/config/beta.yaml
	CLOUD_RUN_MIN_INSTANCES = 0
	LOG_LEVEL_CONFIG = "INFO"
	CORS_ORIGINS_CONFIG = "https://beta.rps.cattail-sw.com"
	SERVICE_ACCOUNT_EMAIL = sa-$(SERVICE_NAME)@$(GCP_PROJECT_ID_BETA).iam.gserviceaccount.com
else # dev (local setup, or deploying a dev instance to cloud)
	TARGET_GCP_PROJECT_ID = $(GCP_PROJECT_ID_DEV)
	CLOUD_RUN_SERVICE_NAME = $(SERVICE_NAME)-api-dev
	GCS_BUCKET_APP_DATA = $(SERVICE_NAME)-app-data-dev
	GCS_PREFIX_APP_DATA = dev/
	GCS_BUCKET_LOG_EXPORTS = $(SERVICE_NAME)-log-exports-dev
	CONFIG_FILE_PATH_IN_CONTAINER = /app/config/dev.yaml
	CLOUD_RUN_MIN_INSTANCES = 0
	LOG_LEVEL_CONFIG = "DEBUG"
	CORS_ORIGINS_CONFIG = "http://localhost:3000,http://localhost:5173,https://dev.yourdomain.com" # Add dev frontend URL
	SERVICE_ACCOUNT_EMAIL = sa-$(SERVICE_NAME)@$(GCP_PROJECT_ID_DEV).iam.gserviceaccount.com
endif

# ADK Model configuration (using Vertex AI for cloud environments)
ADK_MODEL ?= gemini-2.0-flash

# JWT Secret name in Secret Manager (consistent across environments, values differ)
# Note: The secret NAME in Secret Manager is different from the ENV VAR name
# Secret Manager name: rps-jwt-secret
# Environment variable: JWT_SECRET_KEY
JWT_SECRET_NAME_IN_SM = $(SERVICE_NAME)-jwt-secret

# --- Helper Commands ---
.PHONY: help
help:
	@echo "Makefile for $(SERVICE_NAME) System"
	@echo ""
	@echo "Usage: make [target] ENV=[dev|beta|prod] [OTHER_VARIABLES...]"
	@echo "------------------------------------------------------------------------------------"
	@echo "  VARIABLES:"
	@echo "    ENV                 : Target environment (dev, beta, prod). Default: $(DEFAULT_ENV)."
	@echo "    SERVICE_NAME        : Base name for service and resources. Default: $(SERVICE_NAME)."
	@echo "    IMAGE_TAG           : Docker image tag. Default: $(GIT_VERSION) (current git tag/commit)."
	@echo "    GCP_PROJECT_ID_PROD : GCP Project ID for Production (set in env or .env.mk)."
	@echo "    GCP_PROJECT_ID_BETA : GCP Project ID for Beta (set in env or .env.mk)."
	@echo "    GCP_PROJECT_ID_DEV  : GCP Project ID for Development (set in env or .env.mk)."
	@echo "    NEW_GIT_TAG         : Version for 'make tag-git-release' (e.g., v1.2.3)."
	@echo "------------------------------------------------------------------------------------"
	@echo "  MAIN TARGETS:"
	@echo "    make dev-setup            Set up development environment (copy resources to storage path)."
	@echo "    make build-docker         Build the Docker image tagged with current IMAGE_TAG."
	@echo "    make push-docker          Push current IMAGE_TAG to Artifact Registry for current ENV's project."
	@echo "    make deploy               Build, push, and deploy current IMAGE_TAG to Cloud Run for current ENV."
	@echo "    make deploy-image IMAGE_TAG=<tag> Deploy a specific existing image tag to Cloud Run for current ENV."
	@echo "    make run-local-docker     Build and run the container locally for testing."
	@echo "------------------------------------------------------------------------------------"
	@echo "  RELEASE MANAGEMENT:"
	@echo "    make tag-git-release NEW_GIT_TAG=<version> Create and push a new Git tag."
	@echo "------------------------------------------------------------------------------------"
	@echo "  GCP SETUP (Run once per environment, ensure GCP_PROJECT_ID_* are set):"
	@echo "    make setup-gcp-infra ENV=[dev|beta|prod]  Attempt to create GCS buckets, Artifact Repo, Secret container."
	@echo "------------------------------------------------------------------------------------"
	@echo "  TESTING:"
	@echo "    make test                 Run full test suite with coverage report."
	@echo "    make test-quiet           Run tests in quiet mode with coverage."
	@echo "    make test-chat            Run only chat-related tests with coverage."
	@echo "    make test-unit            Run only unit tests with coverage."
	@echo "    make test-integration     Run only integration tests with coverage."
	@echo "    make test-coverage-html   Generate HTML coverage report (viewable in browser)."
	@echo "    make test-no-coverage     Run tests without coverage for faster execution."
	@echo "    make test-specific TEST_PATH=<path> Run a specific test file or test method."
	@echo "------------------------------------------------------------------------------------"
	@echo "  RESOURCE MANAGEMENT:"
	@echo "    make validate-resources   Validate all resource JSON files for correct structure."
	@echo "    make update-resource-metadata Update timestamps in resource files after manual edits."
	@echo "    make upload-resources     Upload resources to GCS bucket for current ENV."
	@echo "    make download-resources   Download resources from GCS bucket for current ENV."
	@echo "    make deploy-with-resources Deploy application and upload resources in one step."
	@echo "------------------------------------------------------------------------------------"
	@echo "  UTILITIES:"
	@echo "    make logs                 View Cloud Run logs for the current ENV."
	@echo "    make list-config          Show current configuration values based on ENV."
	@echo "    make load-env-mk          (Internal) Loads .env.mk if it exists."

# Attempt to load .env.mk for local overrides of GCP_PROJECT_ID_* etc.
# This file should be in .gitignore
-include .env.mk

.PHONY: load-env-mk
load-env-mk:
	@# This target is now just a dependency placeholder
	@# The actual include happens at the top level above

# Call load-env-mk before most targets that need these variables.
# This ensures .env.mk is sourced if present.
build-docker: load-env-mk
push-docker: load-env-mk
deploy: load-env-mk
deploy-image: load-env-mk
setup-gcp-infra: load-env-mk
logs: load-env-mk
list-config: load-env-mk
run-local-docker: load-env-mk

.PHONY: list-config
list-config:
	@echo "--- Current Configuration for ENV=$(ENV) ---"
	@echo "SERVICE_NAME:                 $(SERVICE_NAME)"
	@echo "TARGET_GCP_PROJECT_ID:        $(TARGET_GCP_PROJECT_ID)"
	@echo "CLOUD_RUN_SERVICE_NAME:       $(CLOUD_RUN_SERVICE_NAME)"
	@echo "IMAGE_NAME_BASE (for push):   $(IMAGE_NAME_BASE)"
	@echo "IMAGE_TAG (for build/push):   $(IMAGE_TAG)"
	@echo "GCS_BUCKET_APP_DATA:          $(GCS_BUCKET_APP_DATA)"
	@echo "GCS_PREFIX_APP_DATA:          $(GCS_PREFIX_APP_DATA)"
	@echo "GCS_BUCKET_LOG_EXPORTS:       $(GCS_BUCKET_LOG_EXPORTS)"
	@echo "CONFIG_FILE_PATH_IN_CONTAINER:$(CONFIG_FILE_PATH_IN_CONTAINER)"
	@echo "JWT_SECRET_NAME_IN_SM:        $(JWT_SECRET_NAME_IN_SM)"
	@echo "SERVICE_ACCOUNT_EMAIL:        $(SERVICE_ACCOUNT_EMAIL)"
	@echo "API_BASE_URL_FOR_APP:         $(API_BASE_URL_FOR_APP)"
	@echo "-------------------------------------------"
	@if [ "$(TARGET_GCP_PROJECT_ID)" = "placeholder-prod-project-id" ] || \
	   [ "$(TARGET_GCP_PROJECT_ID)" = "placeholder-beta-project-id" ] || \
	   [ "$(TARGET_GCP_PROJECT_ID)" = "placeholder-dev-project-id" ]; then \
		echo ""; \
		echo "WARNING: TARGET_GCP_PROJECT_ID is a placeholder. Set GCP_PROJECT_ID_PROD/BETA/DEV environment variables or in .env.mk."; \
		echo ""; \
	fi

# --- Build Targets ---
.PHONY: build-docker
build-docker:
	@make list-config
	@# Determine build tag based on whether TARGET_GCP_PROJECT_ID is a placeholder
	@if echo "$(TARGET_GCP_PROJECT_ID)" | grep -q "placeholder"; then \
		echo "Building Docker image rps-local:$(IMAGE_TAG) (local only - no GCP project set)..."; \
		docker build --build-arg GIT_VERSION=$(IMAGE_TAG) --build-arg BUILD_DATE="$$(date -u +%Y-%m-%dT%H:%M:%SZ)" -t rps-local:$(IMAGE_TAG) -f Dockerfile .; \
	else \
		echo "Building Docker image $(IMAGE_NAME_BASE):$(IMAGE_TAG)..."; \
		docker build --build-arg GIT_VERSION=$(IMAGE_TAG) --build-arg BUILD_DATE="$$(date -u +%Y-%m-%dT%H:%M:%SZ)" -t $(IMAGE_NAME_BASE):$(IMAGE_TAG) -f Dockerfile .; \
	fi
	@echo "Docker image built."

# --- Push Target ---
.PHONY: push-docker
push-docker: build-docker
	@make list-config
	@# Check if we're using a placeholder project ID
	@if echo "$(TARGET_GCP_PROJECT_ID)" | grep -q "placeholder"; then \
		echo "ERROR: Cannot push to Artifact Registry with placeholder project ID."; \
		echo "Please set GCP_PROJECT_ID_$(shell echo $(ENV) | tr '[:lower:]' '[:upper:]') in .env.mk or environment."; \
		exit 1; \
	fi
	@echo "Authenticating Docker with Artifact Registry for $(GCP_REGION)..."
	@gcloud auth configure-docker $(GCP_REGION)-docker.pkg.dev --project=$(TARGET_GCP_PROJECT_ID)
	@echo "Pushing Docker image $(IMAGE_NAME_BASE):$(IMAGE_TAG) to Artifact Registry..."
	@docker push $(IMAGE_NAME_BASE):$(IMAGE_TAG)
	@echo "Docker image pushed."

# --- Deploy Targets ---
# Comma-separated list of environment variables for Cloud Run
CLOUD_RUN_ENV_VARS_LIST = \
	ENV=$(ENV),\
	GCP_PROJECT_ID=$(TARGET_GCP_PROJECT_ID),\
	GCS_BUCKET=$(GCS_BUCKET_APP_DATA),\
	GCS_PREFIX=$(GCS_PREFIX_APP_DATA),\
	CONFIG_FILE=$(CONFIG_FILE_PATH_IN_CONTAINER),\
	LOG_LEVEL=$(LOG_LEVEL_CONFIG),\
	CORS_ALLOWED_ORIGINS='$(CORS_ORIGINS_CONFIG)',\
	PYTHONUNBUFFERED=1,\
	GIT_VERSION=$(IMAGE_TAG),\
	SERVICE_NAME=$(SERVICE_NAME),\
	API_BASE_URL=$(API_BASE_URL_FOR_APP),\
	GOOGLE_GENAI_USE_VERTEXAI=TRUE,\
	GOOGLE_CLOUD_PROJECT=$(TARGET_GCP_PROJECT_ID),\
	GOOGLE_CLOUD_LOCATION=us-central1,\
	ADK_MODEL=$(ADK_MODEL)

.PHONY: deploy
deploy: push-docker
	@make deploy-image IMAGE_TAG=$(IMAGE_TAG) # Calls deploy-image with the current default IMAGE_TAG

.PHONY: deploy-image
deploy-image: load-env-mk # Added dependency
	@make list-config # IMAGE_TAG will be shown as the one passed on cmd line or default
	@# Check if we're using a placeholder project ID
	@if echo "$(TARGET_GCP_PROJECT_ID)" | grep -q "placeholder"; then \
		echo "ERROR: Cannot deploy with placeholder project ID."; \
		echo "Please set GCP_PROJECT_ID_$(shell echo $(ENV) | tr '[:lower:]' '[:upper:]') in .env.mk or environment."; \
		exit 1; \
	fi
	@echo "Deploying $(CLOUD_RUN_SERVICE_NAME) to Cloud Run in $(GCP_REGION) from existing image $(IMAGE_NAME_BASE):$(IMAGE_TAG)..."
	@gcloud run deploy $(CLOUD_RUN_SERVICE_NAME) \
		--image $(IMAGE_NAME_BASE):$(IMAGE_TAG) \
		--platform managed \
		--region $(GCP_REGION) \
		--allow-unauthenticated \
		--port 8080 \
		--service-account=$(SERVICE_ACCOUNT_EMAIL) \
		--set-env-vars="$(CLOUD_RUN_ENV_VARS_LIST)" \
		--set-secrets="JWT_SECRET_KEY=$(JWT_SECRET_NAME_IN_SM):latest" \
		--min-instances=$(CLOUD_RUN_MIN_INSTANCES) \
		--max-instances=$(CLOUD_RUN_MAX_INSTANCES) \
		--concurrency=80 \
		--project=$(TARGET_GCP_PROJECT_ID)
	@echo "Deployment of $(CLOUD_RUN_SERVICE_NAME) with image $(IMAGE_TAG) complete."
	@echo "Service URL: $$(gcloud run services describe $(CLOUD_RUN_SERVICE_NAME) --platform managed --region $(GCP_REGION) --project=$(TARGET_GCP_PROJECT_ID) --format 'value(status.url)')"

# --- Local Development ---
.PHONY: run-local-docker
run-local-docker: build-docker
	@echo "Running Docker container locally..."
	@echo "Access at http://localhost:8080"
	@# Determine which image to run based on whether we have a real project ID
	@if echo "$(TARGET_GCP_PROJECT_ID)" | grep -q "placeholder"; then \
		IMAGE_TO_RUN="rps-local:$(IMAGE_TAG)"; \
	else \
		IMAGE_TO_RUN="$(IMAGE_NAME_BASE):$(IMAGE_TAG)"; \
	fi; \
	docker run -it --rm -p 8080:8080 \
		-e ENV=dev \
		-e GCP_PROJECT_ID=$(GCP_PROJECT_ID_DEV) \
		-e GCS_BUCKET=$(SERVICE_NAME)-app-data-dev \
		-e GCS_PREFIX=dev/ \
		-e CONFIG_FILE=/app/config/dev.yaml \
		-e LOG_LEVEL=DEBUG \
		-e CORS_ALLOWED_ORIGINS="http://localhost:5173,http://localhost:3000,http://localhost:8080" \
		-e JWT_SECRET_KEY="development-secret-key-do-not-use-in-production" \
		-e PYTHONUNBUFFERED=1 \
		-e GIT_VERSION=$(GIT_VERSION) \
		-e SERVICE_NAME=$(SERVICE_NAME) \
		-e PORT=8080 \
		$IMAGE_TO_RUN

# --- Local Development ---
.PHONY: dev-setup
dev-setup: load-env-mk validate-resources
	@echo "=== Setting up development environment ==="
	@echo ""
	@# Determine storage path from config
	@STORAGE_PATH=$$(bash -c "source venv/bin/activate && python scripts/get_storage_path.py"); \
	echo "Storage path: $$STORAGE_PATH"; \
	echo ""; \
	if [ ! -d "$$STORAGE_PATH" ]; then \
		echo "Creating storage directory: $$STORAGE_PATH"; \
		mkdir -p "$$STORAGE_PATH"; \
	fi; \
	if [ "$$(realpath data)" = "$$(realpath $$STORAGE_PATH)" ]; then \
		echo "Storage path is the same as project data directory - resources already in place"; \
	else \
		echo "Copying resources to $$STORAGE_PATH/resources..."; \
		mkdir -p "$$STORAGE_PATH/resources"; \
		cp -r data/resources/* "$$STORAGE_PATH/resources/" 2>/dev/null || true; \
	fi; \
	echo ""; \
	echo "Resources copied successfully!"; \
	echo ""; \
	echo "Storage structure:"; \
	find "$$STORAGE_PATH/resources" -type f -name "*.json" | sort; \
	echo ""; \
	echo "=== Development setup complete ==="
	@echo ""
	@echo "You can now run the server with:"
	@echo "  source venv/bin/activate && python src/python/run_server.py"
	@echo ""
	@echo "Or use PyCharm to run src/python/run_server.py"

.PHONY: deploy-dev-resources
deploy-dev-resources:
	@echo "DEPRECATED: Use 'make dev-setup' instead"
	@$(MAKE) dev-setup

# --- Release Management ---
.PHONY: tag-git-release
tag-git-release: # Expects NEW_GIT_TAG to be set, e.g., make tag-git-release NEW_GIT_TAG=v1.0.0
ifndef NEW_GIT_TAG
	$(error NEW_GIT_TAG is not set. Usage: make tag-git-release NEW_GIT_TAG=vX.Y.Z)
endif
	@echo "Creating Git tag: $(NEW_GIT_TAG)"
	@read -p "Enter commit message for tag $(NEW_GIT_TAG) (Press Enter for default: 'Release $(NEW_GIT_TAG)'): " msg; \
	COMMIT_MSG=$${msg:-Release $(NEW_GIT_TAG)}; \
	git tag -a "$(NEW_GIT_TAG)" -m "$$COMMIT_MSG"
	@echo "Pushing Git tag $(NEW_GIT_TAG) to origin..."
	@git push origin "$(NEW_GIT_TAG)"
	@echo "Git tag $(NEW_GIT_TAG) created and pushed."

# --- GCP Setup ---
.PHONY: setup-gcp-infra
setup-gcp-infra: load-env-mk # Added load-env-mk dependency
	@make list-config
	@# Check if we're using a placeholder project ID
	@if echo "$(TARGET_GCP_PROJECT_ID)" | grep -q "placeholder"; then \
		echo "ERROR: Cannot setup GCP infrastructure with placeholder project ID."; \
		echo "Please set GCP_PROJECT_ID_$(shell echo $(ENV) | tr '[:lower:]' '[:upper:]') in .env.mk or environment."; \
		exit 1; \
	fi
	@echo "--- Setting up GCP infrastructure for ENV=$(ENV) in project $(TARGET_GCP_PROJECT_ID) ---"
	@echo "This is best-effort. Manual verification in GCP Console is recommended."
	@echo ""
	@echo "Ensuring necessary APIs are enabled..."
	@gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com storage.googleapis.com iam.googleapis.com cloudbuild.googleapis.com aiplatform.googleapis.com --project=$(TARGET_GCP_PROJECT_ID) || echo "Failed to enable some APIs or already enabled."
	@echo ""
	@echo "Creating GCS bucket for App Data: gs://$(GCS_BUCKET_APP_DATA)..."
	@gsutil mb -p $(TARGET_GCP_PROJECT_ID) -l $(GCP_REGION) gs://$(GCS_BUCKET_APP_DATA) || echo "Bucket already exists or failed to create."
	@echo "Creating GCS bucket for Log Exports: gs://$(GCS_BUCKET_LOG_EXPORTS)..."
	@gsutil mb -p $(TARGET_GCP_PROJECT_ID) -l $(GCP_REGION) gs://$(GCS_BUCKET_LOG_EXPORTS) || echo "Bucket already exists or failed to create."
	@echo ""
	@echo "Creating Artifact Registry repository '$(ARTIFACT_REGISTRY_REPO)'..."
	@gcloud artifacts repositories create $(ARTIFACT_REGISTRY_REPO) --project=$(TARGET_GCP_PROJECT_ID) \
		--repository-format=docker --location=$(GCP_REGION) --description="Docker images for $(SERVICE_NAME)" || echo "Repository already exists or failed to create."
	@echo ""
	@SA_NAME=sa-$(SERVICE_NAME); \
	echo "Creating Service Account '$$SA_NAME' (full email: $(SERVICE_ACCOUNT_EMAIL))..."; \
	gcloud iam service-accounts create $$SA_NAME --display-name="$(SERVICE_NAME) Application Service Account" --project=$(TARGET_GCP_PROJECT_ID) || echo "Service account $$SA_NAME already exists or failed to create."
	@echo ""
	@echo "Creating Secret Manager secret container for JWT key: '$(JWT_SECRET_NAME_IN_SM)'..."
	@gcloud secrets create $(JWT_SECRET_NAME_IN_SM) --project=$(TARGET_GCP_PROJECT_ID) \
		--replication-policy="automatic" || echo "Secret container already exists or failed to create."
	@echo ""
	@echo "IMPORTANT: You must add the actual secret value (version) to '$(JWT_SECRET_NAME_IN_SM)' manually:"
	@echo "  echo -n \"\$$(openssl rand -base64 32)\" | gcloud secrets versions add $(JWT_SECRET_NAME_IN_SM) --data-file=- --project=$(TARGET_GCP_PROJECT_ID)"
	@echo ""
	@echo "Granting Service Account '$(SERVICE_ACCOUNT_EMAIL)' access to the JWT secret..."
	@gcloud secrets add-iam-policy-binding $(JWT_SECRET_NAME_IN_SM) --project=$(TARGET_GCP_PROJECT_ID) \
		--member="serviceAccount:$(SERVICE_ACCOUNT_EMAIL)" \
		--role="roles/secretmanager.secretAccessor" || echo "Failed to grant secret access or already granted."
	@echo "Granting Service Account '$(SERVICE_ACCOUNT_EMAIL)' GCS bucket access (Object Admin)..."
	@gsutil iam ch serviceAccount:$(SERVICE_ACCOUNT_EMAIL):objectAdmin gs://$(GCS_BUCKET_APP_DATA) || echo "Failed to grant GCS app data bucket access."
	@gsutil iam ch serviceAccount:$(SERVICE_ACCOUNT_EMAIL):objectAdmin gs://$(GCS_BUCKET_LOG_EXPORTS) || echo "Failed to grant GCS log exports bucket access."
	@echo ""
	@echo "Granting Service Account '$(SERVICE_ACCOUNT_EMAIL)' Vertex AI access..."
	@gcloud projects add-iam-policy-binding $(TARGET_GCP_PROJECT_ID) \
		--member="serviceAccount:$(SERVICE_ACCOUNT_EMAIL)" \
		--role="roles/aiplatform.user" || echo "Failed to grant Vertex AI access or already granted."
	@echo ""
	@echo "--- GCP Infrastructure setup for ENV=$(ENV) complete. Please verify in Console. ---"

# --- Testing Targets ---
.PHONY: test
test:
	@echo "Running full test suite with coverage..."
	@bash -c "source venv/bin/activate && python -m pytest test/python/ --cov=src/python/role_play --cov-report=term-missing --cov-fail-under=25"

.PHONY: test-quiet
test-quiet:
	@echo "Running tests in quiet mode with coverage..."
	@bash -c "source venv/bin/activate && python -m pytest test/python/ -q --cov=src/python/role_play --cov-report=term-missing --cov-fail-under=25"

.PHONY: test-chat
test-chat:
	@echo "Running chat-related tests with coverage..."
	@bash -c "source venv/bin/activate && python -m pytest test/python/ -k 'chat' --cov=src/python/role_play/chat --cov-report=term-missing --cov-fail-under=0"

.PHONY: test-unit
test-unit:
	@echo "Running unit tests with coverage..."
	@bash -c "source venv/bin/activate && python -m pytest test/python/unit/ --cov=src/python/role_play --cov-report=term-missing --cov-fail-under=0"

.PHONY: test-integration
test-integration:
	@echo "Running integration tests with coverage..."
	@bash -c "source venv/bin/activate && python -m pytest test/python/integration/ --cov=src/python/role_play --cov-report=term-missing --cov-fail-under=0"

.PHONY: test-coverage-html
test-coverage-html:
	@echo "Generating HTML coverage report..."
	@bash -c "source venv/bin/activate && python -m pytest test/python/ --cov=src/python/role_play --cov-report=html --cov-fail-under=0"
	@echo "Coverage report generated at: test/python/htmlcov/index.html"
	@echo "Open in browser: file://$(shell pwd)/test/python/htmlcov/index.html"

.PHONY: test-no-coverage
test-no-coverage:
	@echo "Running tests without coverage (faster)..."
	@bash -c "source venv/bin/activate && python -m pytest test/python/ -v"

.PHONY: test-specific
test-specific:
ifndef TEST_PATH
	$(error TEST_PATH is not set. Usage: make test-specific TEST_PATH="test/python/unit/chat/test_chat_logger.py::TestChatLogger::test_read_only_session_history_integration")
endif
	@echo "Running specific test: $(TEST_PATH)"
	@bash -c "source venv/bin/activate && python -m pytest '$(TEST_PATH)' -v --cov=src/python/role_play --cov-report=term-missing --cov-fail-under=0"

# --- Resource Management ---
.PHONY: validate-resources
validate-resources:
	@echo "Validating resource JSON files..."
	@bash -c "source venv/bin/activate && python scripts/validate_resources.py data/resources/"

.PHONY: update-resource-metadata
update-resource-metadata:
	@echo "Updating resource metadata (timestamps)..."
	@bash -c "source venv/bin/activate && python scripts/update_resource_metadata.py data/resources/"

.PHONY: upload-resources
upload-resources: load-env-mk validate-resources
	@make list-config
	@# Check if we're using a placeholder project ID
	@if echo "$(TARGET_GCP_PROJECT_ID)" | grep -q "placeholder"; then \
		echo "ERROR: Cannot upload resources with placeholder project ID."; \
		echo "Please set GCP_PROJECT_ID_$(shell echo $(ENV) | tr '[:lower:]' '[:upper:]') in .env.mk or environment."; \
		exit 1; \
	fi
	@echo "Uploading resources to GCS bucket gs://$(GCS_BUCKET_APP_DATA)/$(GCS_PREFIX_APP_DATA)resources/..."
	@gsutil -m cp -r data/resources/* gs://$(GCS_BUCKET_APP_DATA)/$(GCS_PREFIX_APP_DATA)resources/
	@echo "Resources uploaded successfully."

.PHONY: download-resources
download-resources: load-env-mk
	@make list-config
	@# Check if we're using a placeholder project ID
	@if echo "$(TARGET_GCP_PROJECT_ID)" | grep -q "placeholder"; then \
		echo "ERROR: Cannot download resources with placeholder project ID."; \
		echo "Please set GCP_PROJECT_ID_$(shell echo $(ENV) | tr '[:lower:]' '[:upper:]') in .env.mk or environment."; \
		exit 1; \
	fi
	@echo "Downloading resources from GCS bucket gs://$(GCS_BUCKET_APP_DATA)/$(GCS_PREFIX_APP_DATA)resources/..."
	@mkdir -p data/resources
	@gsutil -m cp -r gs://$(GCS_BUCKET_APP_DATA)/$(GCS_PREFIX_APP_DATA)resources/* data/resources/
	@echo "Resources downloaded successfully."


.PHONY: deploy-with-resources
deploy-with-resources: validate-resources upload-resources deploy
	@echo "Deployment with resources completed."

# --- Utilities ---
.PHONY: logs
logs:
	@make list-config
	@echo "Fetching logs for $(CLOUD_RUN_SERVICE_NAME) in $(GCP_REGION) from project $(TARGET_GCP_PROJECT_ID)..."
	@gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$(CLOUD_RUN_SERVICE_NAME) AND resource.labels.configuration_name=$(CLOUD_RUN_SERVICE_NAME)" \
		--project=$(TARGET_GCP_PROJECT_ID) --limit=50 --format="table(timestamp,logName,severity,jsonPayload.message)"

# Default target
.DEFAULT_GOAL := help

# Example .env.mk file (DO NOT COMMIT THIS FILE - add to .gitignore)
# Create this file in your project root to set your actual GCP Project IDs.
#
# GCP_PROJECT_ID_PROD=your-actual-prod-project-id
# GCP_PROJECT_ID_BETA=your-actual-beta-project-id
# GCP_PROJECT_ID_DEV=your-actual-dev-project-id
# SERVICE_NAME=rps # Can also be set here if you don't want to pass it on cmd line