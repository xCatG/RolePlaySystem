# Stage 1: Build Vue.js Frontend
# Use a specific Node.js version for reproducibility
FROM node:18.18-slim as frontend-builder

# Set working directory for frontend
WORKDIR /app/frontend

# Copy frontend package.json and package-lock.json
# Only copy these first to leverage Docker layer caching for dependencies
COPY src/ts/role_play/ui/package.json src/ts/role_play/ui/package-lock.json* ./

# Install frontend dependencies
RUN npm ci --legacy-peer-deps

# Copy the rest of the frontend source code
COPY src/ts/role_play/ui/ ./

# Build the frontend application
# Ensure your package.json's "build" script outputs to 'dist'
RUN npm run build

# Stage 2: Setup Python Backend and Serve Frontend
# Use a specific Python version for reproducibility
FROM python:3.11.5-slim

WORKDIR /app

# Install system dependencies if needed (e.g., gcc for some Python packages)
# RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=off
ENV PIP_DISABLE_PIP_VERSION_CHECK=on

# Copy Python requirements file
COPY src/python/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application code
COPY src/python/ ./src/python/
COPY config/ ./config/

# Copy built frontend assets from the frontend-builder stage
# Assuming the frontend build output is in /app/frontend/dist
COPY --from=frontend-builder /app/frontend/dist /app/static_frontend

# Expose the port the app runs on. Cloud Run injects PORT, typically 8080.
EXPOSE 8080

# Command to run the application
CMD ["python", "src/python/run_server.py"]