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

# --- Helper ---
help:
	@echo "Available commands:"
	@echo "  build            - Build the Docker image"
	@echo "  run              - Build and run the Docker container in detached mode"
	@echo "  run-interactive  - Build and run the Docker container in interactive mode (removes on exit)"
	@echo "  stop             - Stop and remove the running Docker container"
	@echo "  logs             - View logs of the running container"
	@echo "  clean-image      - Remove the Docker image"
	@echo "  clean            - Stop container, remove container, and remove image"
	@echo "  help             - Show this help message"

.PHONY: build run run-interactive stop logs clean-image clean help