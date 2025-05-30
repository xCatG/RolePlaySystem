# Makefile for Dockerized Role Play System

# --- Configuration ---
# Image name for your Docker container
IMAGE_NAME := role-play-system
# Tag for your Docker image (e.g., latest, v1.0)
IMAGE_TAG := latest
# Container name when running
CONTAINER_NAME := rps-app
# Port mapping: <host_port>:<container_port>
PORT_MAPPING := 8000:8000
# Data volume mapping: <host_path_to_data>:/app/backend/data
DATA_VOLUME_MOUNT := $(shell pwd)/rps_data_volume:/app/backend/data
# Environment file (optional, for local run)
ENV_FILE := .env.prod

# --- Cloud Run Test Configuration ---
# Image name for Cloud Run test
CLOUD_RUN_IMAGE_NAME := rps-poc
# Tag for Cloud Run test image
CLOUD_RUN_IMAGE_TAG := test
# Container name for Cloud Run test
CLOUD_RUN_CONTAINER_NAME := rps-cloud-run-test
# Port for Cloud Run test (simulating Cloud Run's PORT env var)
CLOUD_RUN_PORT := 8080
# Test JWT secret for local Cloud Run simulation
TEST_JWT_SECRET := test-jwt-secret-not-for-production

# --- Docker Commands ---

# Build the Docker image
build:
	@echo "Building Docker image $(IMAGE_NAME):$(IMAGE_TAG)..."
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .

# Run the Docker container
run: build
	@echo "Running Docker container $(CONTAINER_NAME)..."
	@echo "Access the application at http://localhost:$(firstword $(subst :, ,$(PORT_MAPPING)))"
	@echo "Persistent data will be stored in $(firstword $(subst :, ,$(DATA_VOLUME_MOUNT))) on your host."
	# Create the data directory on the host if it doesn't exist
	mkdir -p $(firstword $(subst :, ,$(DATA_VOLUME_MOUNT)))
	docker run -d \
		--name $(CONTAINER_NAME) \
		-p $(PORT_MAPPING) \
		-v "$(DATA_VOLUME_MOUNT)" \
		$(if $(wildcard $(ENV_FILE)),--env-file $(ENV_FILE)) \
		$(IMAGE_NAME):$(IMAGE_TAG)

# Run container in interactive mode (for debugging)
run-interactive: build
	@echo "Running Docker container $(CONTAINER_NAME) interactively..."
	# Create the data directory on the host if it doesn't exist
	mkdir -p $(firstword $(subst :, ,$(DATA_VOLUME_MOUNT)))
	docker run --rm -it \
		--name $(CONTAINER_NAME)-interactive \
		-p $(PORT_MAPPING) \
		-v "$(DATA_VOLUME_MOUNT)" \
		$(if $(wildcard $(ENV_FILE)),--env-file $(ENV_FILE)) \
		$(IMAGE_NAME):$(IMAGE_TAG)

# Stop the running Docker container
stop:
	@echo "Stopping Docker container $(CONTAINER_NAME)..."
	docker stop $(CONTAINER_NAME) || echo "Container $(CONTAINER_NAME) not running or already stopped."
	docker rm $(CONTAINER_NAME) || echo "Container $(CONTAINER_NAME) not found or already removed."

# View logs of the running container
logs:
	@echo "Showing logs for container $(CONTAINER_NAME)..."
	docker logs -f $(CONTAINER_NAME)

# Remove the Docker image
clean-image:
	@echo "Removing Docker image $(IMAGE_NAME):$(IMAGE_TAG)..."
	docker rmi $(IMAGE_NAME):$(IMAGE_TAG) || echo "Image $(IMAGE_NAME):$(IMAGE_TAG) not found."

# Full clean: stop container, remove container, remove image
clean: stop clean-image
	@echo "Full clean complete."

# --- Cloud Run Test Commands ---

# Build image for Cloud Run testing
build-cloud-run:
	@echo "Building Docker image for Cloud Run test: $(CLOUD_RUN_IMAGE_NAME):$(CLOUD_RUN_IMAGE_TAG)..."
	docker build -t $(CLOUD_RUN_IMAGE_NAME):$(CLOUD_RUN_IMAGE_TAG) .

# Test Cloud Run locally (simulating Cloud Run environment)
test-cloud-run: build-cloud-run
	@echo "Starting Cloud Run test container..."
	@echo "This simulates the Cloud Run environment with:"
	@echo "  - PORT environment variable set to $(CLOUD_RUN_PORT)"
	@echo "  - ENVIRONMENT set to 'poc'"
	@echo "  - Ephemeral storage at /tmp/data"
	@echo "  - Test JWT secret (not for production)"
	@echo ""
	@echo "Access the application at http://localhost:$(CLOUD_RUN_PORT)"
	@echo "Health check: http://localhost:$(CLOUD_RUN_PORT)/health"
	@echo ""
	docker run --rm -it \
		--name $(CLOUD_RUN_CONTAINER_NAME) \
		-p $(CLOUD_RUN_PORT):$(CLOUD_RUN_PORT) \
		-e PORT=$(CLOUD_RUN_PORT) \
		-e ENVIRONMENT=poc \
		-e JWT_SECRET_KEY="$(TEST_JWT_SECRET)" \
		-e STORAGE_PATH=/tmp/data \
		-e CORS_ORIGINS="https://poc.rps.cattail-sw.com,http://localhost:$(CLOUD_RUN_PORT)" \
		$(CLOUD_RUN_IMAGE_NAME):$(CLOUD_RUN_IMAGE_TAG)

# Test Cloud Run in detached mode (background)
test-cloud-run-detached: build-cloud-run
	@echo "Starting Cloud Run test container in background..."
	@echo "Container name: $(CLOUD_RUN_CONTAINER_NAME)"
	@echo "Access at: http://localhost:$(CLOUD_RUN_PORT)"
	docker run -d \
		--name $(CLOUD_RUN_CONTAINER_NAME) \
		-p $(CLOUD_RUN_PORT):$(CLOUD_RUN_PORT) \
		-e PORT=$(CLOUD_RUN_PORT) \
		-e ENVIRONMENT=poc \
		-e JWT_SECRET_KEY="$(TEST_JWT_SECRET)" \
		-e STORAGE_PATH=/tmp/data \
		-e CORS_ORIGINS="https://poc.rps.cattail-sw.com,http://localhost:$(CLOUD_RUN_PORT)" \
		$(CLOUD_RUN_IMAGE_NAME):$(CLOUD_RUN_IMAGE_TAG)
	@echo "Container started. Use 'make test-cloud-run-logs' to view logs."
	@echo "Use 'make test-cloud-run-stop' to stop the container."

# View logs of Cloud Run test container
test-cloud-run-logs:
	@echo "Showing logs for Cloud Run test container..."
	docker logs -f $(CLOUD_RUN_CONTAINER_NAME)

# Stop Cloud Run test container
test-cloud-run-stop:
	@echo "Stopping Cloud Run test container..."
	docker stop $(CLOUD_RUN_CONTAINER_NAME) || echo "Container not running."
	docker rm $(CLOUD_RUN_CONTAINER_NAME) || echo "Container not found."

# Health check for Cloud Run test
test-cloud-run-health:
	@echo "Checking health of Cloud Run test container..."
	@curl -s http://localhost:$(CLOUD_RUN_PORT)/health | python3 -m json.tool || echo "Health check failed. Is the container running?"

# Clean up Cloud Run test images
clean-cloud-run:
	@echo "Removing Cloud Run test image..."
	docker rmi $(CLOUD_RUN_IMAGE_NAME):$(CLOUD_RUN_IMAGE_TAG) || echo "Image not found."

# --- Helper ---
help:
	@echo "Available commands:"
	@echo "  === Standard Docker Commands ==="
	@echo "  build            - Build the Docker image"
	@echo "  run              - Build and run the Docker container in detached mode"
	@echo "  run-interactive  - Build and run the Docker container in interactive mode"
	@echo "  stop             - Stop and remove the running Docker container"
	@echo "  logs             - View logs of the running container"
	@echo "  clean-image      - Remove the Docker image"
	@echo "  clean            - Stop container, remove container, and remove image"
	@echo ""
	@echo "  === Cloud Run Test Commands ==="
	@echo "  test-cloud-run   - Test the app simulating Cloud Run environment (interactive)"
	@echo "  test-cloud-run-detached - Test in background mode"
	@echo "  test-cloud-run-logs     - View logs of Cloud Run test container"
	@echo "  test-cloud-run-stop     - Stop Cloud Run test container"
	@echo "  test-cloud-run-health   - Check health endpoint of Cloud Run test"
	@echo "  build-cloud-run  - Just build the Cloud Run test image"
	@echo "  clean-cloud-run  - Remove Cloud Run test image"
	@echo ""
	@echo "  help             - Show this help message"

.PHONY: build run run-interactive stop logs clean-image clean help \
	build-cloud-run test-cloud-run test-cloud-run-detached test-cloud-run-logs \
	test-cloud-run-stop test-cloud-run-health clean-cloud-run