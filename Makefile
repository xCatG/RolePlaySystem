# Makefile for Role Play System (RPS)

# --- Configuration ---
# SERVICE_NAME: Used for naming resources. Override for different services.
SERVICE_NAME ?= rps
# DEFAULT_ENV: Default environment if ENV is not set.
DEFAULT_ENV ?= dev
# ENV: Current operational environment (dev, beta, prod). Set via command line: make deploy ENV=prod
ENV ?= $(DEFAULT_ENV)

# GCP Region for deployments
GCP_REGION ?= us-central1

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
GCP_PROJECT_ID_PROD ?= "placeholder-prod-project-id"
GCP_PROJECT_ID_BETA ?= "placeholder-beta-project-id"
GCP_PROJECT_ID_DEV  ?= "placeholder-dev-project-id"

TARGET_GCP_PROJECT_ID = ""
CLOUD_RUN_SERVICE_NAME = ""
GCS_BUCKET_APP_DATA = ""
GCS_BUCKET_LOG_EXPORTS = "" # Optional
CONFIG_FILE_PATH_IN_CONTAINER = ""
CLOUD_RUN_MIN_INSTANCES = 0
CLOUD_RUN_MAX_INSTANCES = 10
LOG_LEVEL_CONFIG = "INFO"
CORS_ORIGINS_CONFIG = "http://localhost:3000,http://localhost:5173" # Default for local dev
SERVICE_ACCOUNT_EMAIL = "" # Expected to be set per environment

ifeq ($(ENV),prod)
	TARGET_GCP_PROJECT_ID = $(GCP_PROJECT_ID_PROD)
	CLOUD_RUN_SERVICE_NAME = $(SERVICE_NAME)-api-prod
	GCS_BUCKET_APP_DATA = $(SERVICE_NAME)-app-data-prod
	GCS_BUCKET_LOG_EXPORTS = $(SERVICE_NAME)-log-exports-prod
	CONFIG_FILE_PATH_IN_CONTAINER = /app/config/prod.yaml
	CLOUD_RUN_MIN_INSTANCES = 1
	LOG_LEVEL_CONFIG = "WARNING"
	CORS_ORIGINS_CONFIG = "https://prod.yourdomain.com" # Replace with actual prod frontend URL
	SERVICE_ACCOUNT_EMAIL = sa-$(SERVICE_NAME)@$(GCP_PROJECT_ID_PROD).iam.gserviceaccount.com
else ifeq ($(ENV),beta)
	TARGET_GCP_PROJECT_ID = $(GCP_PROJECT_ID_BETA)
	CLOUD_RUN_SERVICE_NAME = $(SERVICE_NAME)-api-beta
	GCS_BUCKET_APP_DATA = $(SERVICE_NAME)-app-data-beta
	GCS_BUCKET_LOG_EXPORTS = $(SERVICE_NAME)-log-exports-beta
	CONFIG_FILE_PATH_IN_CONTAINER = /app/config/beta.yaml
	CLOUD_RUN_MIN_INSTANCES = 0
	LOG_LEVEL_CONFIG = "INFO"
	CORS_ORIGINS_CONFIG = "https://beta.yourdomain.com" # Replace with actual beta frontend URL
	SERVICE_ACCOUNT_EMAIL = sa-$(SERVICE_NAME)@$(GCP_PROJECT_ID_BETA).iam.gserviceaccount.com
else # dev (local setup, or deploying a dev instance to cloud)
	TARGET_GCP_PROJECT_ID = $(GCP_PROJECT_ID_DEV)
	CLOUD_RUN_SERVICE_NAME = $(SERVICE_NAME)-api-dev
	GCS_BUCKET_APP_DATA = $(SERVICE_NAME)-app-data-dev
	GCS_BUCKET_LOG_EXPORTS = $(SERVICE_NAME)-log-exports-dev
	CONFIG_FILE_PATH_IN_CONTAINER = /app/config/dev.yaml
	CLOUD_RUN_MIN_INSTANCES = 0
	LOG_LEVEL_CONFIG = "DEBUG"
	CORS_ORIGINS_CONFIG = "http://localhost:3000,http://localhost:5173,https://dev.yourdomain.com" # Add dev frontend URL
	SERVICE_ACCOUNT_EMAIL = sa-$(SERVICE_NAME)@$(GCP_PROJECT_ID_DEV).iam.gserviceaccount.com
endif

# JWT Secret name in Secret Manager (consistent across environments, values differ)
JWT_SECRET_NAME_IN_SM = $(SERVICE_NAME)-jwt-signing-key

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
	@echo "    make build-docker         Build the Docker image tagged with $(IMAGE_TAG)."
	@echo "    make push-docker          Push image $(IMAGE_TAG) to Artifact Registry for current ENV's project."
	@echo "    make deploy               Build, push, and deploy image $(IMAGE_TAG) to Cloud Run for current ENV."
	@echo "    make deploy-image IMAGE_TAG=<tag> Deploy a specific existing image tag to Cloud Run for current ENV."
	@echo "    make run-local-docker     Build and run the container locally for testing."
	@echo "------------------------------------------------------------------------------------"
	@echo "  RELEASE MANAGEMENT:"
	@echo "    make tag-git-release NEW_GIT_TAG=<version> Create and push a new Git tag."
	@echo "------------------------------------------------------------------------------------"
	@echo "  GCP SETUP (Run once per environment, ensure GCP_PROJECT_ID_* are set):"
	@echo "    make setup-gcp-infra ENV=[dev|beta|prod]  Attempt to create GCS buckets, Artifact Repo, Secret container."
	@echo "------------------------------------------------------------------------------------"
	@echo "  UTILITIES:"
	@echo "    make logs                 View Cloud Run logs for the current ENV."
	@echo "    make list-config          Show current configuration values based on ENV."
	@echo "    make load-env-mk          (Internal) Loads .env.mk if it exists."

# Attempt to load .env.mk for local overrides of GCP_PROJECT_ID_* etc.
# This file should be in .gitignore
.PHONY: load-env-mk
load-env-mk:
	$(eval -include .env.mk)

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
	@echo "GCS_BUCKET_LOG_EXPORTS:       $(GCS_BUCKET_LOG_EXPORTS)"
	@echo "CONFIG_FILE_PATH_IN_CONTAINER:$(CONFIG_FILE_PATH_IN_CONTAINER)"
	@echo "JWT_SECRET_NAME_IN_SM:        $(JWT_SECRET_NAME_IN_SM)"
	@echo "SERVICE_ACCOUNT_EMAIL:        $(SERVICE_ACCOUNT_EMAIL)"
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
	@echo "Building Docker image $(IMAGE_NAME_BASE):$(IMAGE_TAG)..."
	@docker build -t $(IMAGE_NAME_BASE):$(IMAGE_TAG) -f Dockerfile .
	@echo "Docker image $(IMAGE_NAME_BASE):$(IMAGE_TAG) built."

# --- Push Target ---
.PHONY: push-docker
push-docker: build-docker
	@make list-config
	@echo "Authenticating Docker with Artifact Registry for $(GCP_REGION)..."
	@gcloud auth configure-docker $(GCP_REGION)-docker.pkg.dev --project=$(TARGET_GCP_PROJECT_ID)
	@echo "Pushing Docker image $(IMAGE_NAME_BASE):$(IMAGE_TAG) to Artifact Registry..."
	@docker push $(IMAGE_NAME_BASE):$(IMAGE_TAG)
	@echo "Docker image pushed."

# --- Deploy Targets ---
.PHONY: deploy
deploy: push-docker
	@make list-config
	@echo "Deploying $(CLOUD_RUN_SERVICE_NAME) to Cloud Run in $(GCP_REGION) from image $(IMAGE_NAME_BASE):$(IMAGE_TAG)..."
	@gcloud run deploy $(CLOUD_RUN_SERVICE_NAME) \
		--image $(IMAGE_NAME_BASE):$(IMAGE_TAG) \
		--platform managed \
		--region $(GCP_REGION) \
		--allow-unauthenticated \
		--port 8080 \
		--service-account=$(SERVICE_ACCOUNT_EMAIL) \
		--set-env-vars="ENV=$(ENV)" \
		--set-env-vars="GCP_PROJECT_ID=$(TARGET_GCP_PROJECT_ID)" \
		--set-env-vars="GCS_BUCKET=$(GCS_BUCKET_APP_DATA)" \
		--set-env-vars="GCS_PREFIX=$(ENV)/" \
		--set-env-vars="CONFIG_FILE=$(CONFIG_FILE_PATH_IN_CONTAINER)" \
		--set-env-vars="LOG_LEVEL=$(LOG_LEVEL_CONFIG)" \
		--set-env-vars="CORS_ALLOWED_ORIGINS=$(CORS_ORIGINS_CONFIG)" \
		--set-env-vars="PYTHONUNBUFFERED=1" \
		--set-env-vars="GIT_VERSION=$(GIT_VERSION)" \
		--set-env-vars="SERVICE_NAME=$(SERVICE_NAME)" \
		--set-secrets="JWT_SECRET_KEY=$(JWT_SECRET_NAME_IN_SM):latest" \
		--min-instances=$(CLOUD_RUN_MIN_INSTANCES) \
		--max-instances=$(CLOUD_RUN_MAX_INSTANCES) \
		--concurrency=80 \
		--project=$(TARGET_GCP_PROJECT_ID)
	@echo "Deployment of $(CLOUD_RUN_SERVICE_NAME) complete."
	@echo "Service URL: $$(gcloud run services describe $(CLOUD_RUN_SERVICE_NAME) --platform managed --region $(GCP_REGION) --project=$(TARGET_GCP_PROJECT_ID) --format 'value(status.url)')"

.PHONY: deploy-image
deploy-image: # Expects ENV and IMAGE_TAG (for the specific image) to be set
	@make list-config # IMAGE_TAG will be shown as the one passed on cmd line
	@echo "Deploying $(CLOUD_RUN_SERVICE_NAME) to Cloud Run in $(GCP_REGION) from existing image $(IMAGE_NAME_BASE):$(IMAGE_TAG)..."
	@gcloud run deploy $(CLOUD_RUN_SERVICE_NAME) \
		--image $(IMAGE_NAME_BASE):$(IMAGE_TAG) \
		--platform managed \
		--region $(GCP_REGION) \
		--allow-unauthenticated \
		--port 8080 \
		--service-account=$(SERVICE_ACCOUNT_EMAIL) \
		--set-env-vars="ENV=$(ENV)" \
		--set-env-vars="GCP_PROJECT_ID=$(TARGET_GCP_PROJECT_ID)" \
		--set-env-vars="GCS_BUCKET=$(GCS_BUCKET_APP_DATA)" \
		--set-env-vars="GCS_PREFIX=$(ENV)/" \
		--set-env-vars="CONFIG_FILE=$(CONFIG_FILE_PATH_IN_CONTAINER)" \
		--set-env-vars="LOG_LEVEL=$(LOG_LEVEL_CONFIG)" \
		--set-env-vars="CORS_ALLOWED_ORIGINS=$(CORS_ORIGINS_CONFIG)" \
		--set-env-vars="PYTHONUNBUFFERED=1" \
		--set-env-vars="GIT_VERSION=$(IMAGE_TAG)" \
		--set-env-vars="SERVICE_NAME=$(SERVICE_NAME)" \
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
	@echo "Running Docker container $(IMAGE_NAME_BASE):$(IMAGE_TAG) locally..."
	@echo "Access at http://localhost:8080"
	@docker run -it --rm -p 8080:8080 \
		-e ENV=dev \
		-e GCP_PROJECT_ID=$(GCP_PROJECT_ID_DEV) \
		-e GCS_BUCKET=$(SERVICE_NAME)-app-data-dev \
		-e GCS_PREFIX=dev/ \
		-e CONFIG_FILE=/app/config/dev.yaml \
		-e LOG_LEVEL=DEBUG \
		-e CORS_ALLOWED_ORIGINS="http://localhost:5173,http://localhost:3000" \
		-e JWT_SECRET_KEY="development-secret-key-do-not-use-in-production" \
		-e PYTHONUNBUFFERED=1 \
		-e GIT_VERSION=$(GIT_VERSION) \
		-e SERVICE_NAME=$(SERVICE_NAME) \
		-e PORT=8080 \
		$(IMAGE_NAME_BASE):$(IMAGE_TAG)

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
setup-gcp-infra: # Expects ENV to be set to determine TARGET_GCP_PROJECT_ID etc.
	@make list-config
	@echo "--- Attempting to setup GCP infrastructure for ENV=$(ENV) in project $(TARGET_GCP_PROJECT_ID) ---"
	@echo "This is best-effort. Manual verification in GCP Console is recommended."
	@echo ""
	@echo "Ensuring necessary APIs are enabled..."
	@gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com storage.googleapis.com iam.googleapis.com cloudbuild.googleapis.com --project=$(TARGET_GCP_PROJECT_ID) || echo "Failed to enable some APIs or already enabled."
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
	@echo "Creating Service Account '$(SERVICE_ACCOUNT_EMAIL)'..."
	@gcloud iam service-accounts create sa-$(SERVICE_NAME) --display-name="$(SERVICE_NAME) Application Service Account" --project=$(TARGET_GCP_PROJECT_ID) || echo "Service account sa-$(SERVICE_NAME) already exists or failed to create."
	@echo ""
	@echo "Creating Secret Manager secret container for JWT key: '$(JWT_SECRET_NAME_IN_SM)'..."
	@gcloud secrets create $(JWT_SECRET_NAME_IN_SM) --project=$(TARGET_GCP_PROJECT_ID) \
		--replication-policy="automatic" --description="JWT signing key for $(SERVICE_NAME) $(ENV) environment" || echo "Secret container already exists or failed to create."
	@echo "IMPORTANT: You must add the actual secret value (version) to '$(JWT_SECRET_NAME_IN_SM)' manually or via script."
	@echo "Example: echo -n \"your-secure-random-string\" | gcloud secrets versions add $(JWT_SECRET_NAME_IN_SM) --data-file=- --project=$(TARGET_GCP_PROJECT_ID)"
	@echo ""
	@echo "Granting Service Account '$(SERVICE_ACCOUNT_EMAIL)' access to the JWT secret..."
	@gcloud secrets add-iam-policy-binding $(JWT_SECRET_NAME_IN_SM) --project=$(TARGET_GCP_PROJECT_ID) \
		--member="serviceAccount:$(SERVICE_ACCOUNT_EMAIL)" \
		--role="roles/secretmanager.secretAccessor" || echo "Failed to grant secret access or already granted."
	@echo "Granting Service Account '$(SERVICE_ACCOUNT_EMAIL)' GCS bucket access (Object Admin)..."
	@gsutil iam ch serviceAccount:$(SERVICE_ACCOUNT_EMAIL):objectAdmin gs://$(GCS_BUCKET_APP_DATA) || echo "Failed to grant GCS app data bucket access."
	@gsutil iam ch serviceAccount:$(SERVICE_ACCOUNT_EMAIL):objectAdmin gs://$(GCS_BUCKET_LOG_EXPORTS) || echo "Failed to grant GCS log exports bucket access."
	@echo ""
	@echo "--- GCP Infrastructure setup attempt for ENV=$(ENV) complete. Please verify. ---"

# --- Utilities ---
.PHONY: logs
logs:
	@make list-config
	@echo "Fetching logs for $(CLOUD_RUN_SERVICE_NAME) in $(GCP_REGION) from project $(TARGET_GCP_PROJECT_ID)..."
	@gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$(CLOUD_RUN_SERVICE_NAME) AND resource.labels.configuration_name=$(CLOUD_RUN_SERVICE_NAME)" \
		--project=$(TARGET_GCP_PROJECT_ID) --limit=50 --format="table(timestamp,logName,severity,jsonPayload.message)"

# Default target
.DEFAULT_GOAL := help