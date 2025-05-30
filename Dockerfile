# Stage 1: Build Vue.js Frontend
FROM node:18-alpine AS builder
WORKDIR /app/frontend

# Copy package.json and package-lock.json (or yarn.lock)
COPY src/ts/role_play/ui/package.json src/ts/role_play/ui/package-lock.json* ./
# If you use yarn, copy yarn.lock instead and use yarn install

# Install dependencies
RUN npm ci --loglevel warn

# Copy the rest of the frontend source code
COPY src/ts/role_play/ui/ ./

# Build the frontend
# Ensure your build script outputs to a known directory, e.g., 'dist'
RUN npm run build --loglevel warn

# Stage 2: Python Backend
FROM python:3.12-slim-bookworm
WORKDIR /app

# Set environment variables for Python
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
# PORT will be set by Cloud Run. Our app will read this.
# ENV PORT=8000 (No longer needed to set here if app reads from env)
ENV ENVIRONMENT=poc # Default environment, can be overridden by Cloud Run env var setting

# Create a non-root user and group
RUN groupadd -r appgroup && useradd --no-log-init -r -g appgroup -u 1000 appuser

# Create necessary directories and set permissions
# /app/static_data for scenarios.json (if copied there)
# /app/data or /tmp/data for FileStorage (if used ephemerally)
# The STORAGE_PATH env var will point to /tmp/data for PoC
RUN mkdir -p /app/static_data /tmp/data && \
    chown -R appuser:appgroup /app /tmp/data && \
    chmod -R 775 /app && \
    chmod 777 /tmp/data # /tmp/data needs to be writable by the app

# Copy requirements first to leverage Docker cache
COPY src/python/requirements.txt .
# Consider requirements-all.txt if that's your consolidated list for prod/poc
# COPY src/python/requirements-all.txt ./requirements.txt 

# Install Python dependencies
# --no-cache-dir reduces image size
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY src/python/ ./src/python/

# Copy configuration files
COPY config/ ./config/

# Copy static data like scenarios.json
# The source is 'data/scenarios.json' in your repo root
# and it needs to be in '/app/static_data/' inside the container
# for ContentLoader to find it
COPY data/scenarios.json /app/static_data/scenarios.json

# Copy built frontend from builder stage to the location FastAPI serves it from
COPY --from=builder /app/frontend/dist /app/static_frontend/
# Ensure static_frontend is the correct directory your BaseServer expects

# Ensure all files in /app are owned by appuser
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose the port the app will listen on (Cloud Run will map to this)
# This is informational; Cloud Run uses the PORT env var.
EXPOSE 8000 

# Command to run the application
# Use gunicorn for better performance in a "production-like" PoC on Cloud Run
# The port 0.0.0.0:${PORT} is important for gunicorn to respect Cloud Run's PORT
# Your run_server.py's main() function already handles loading config and starting uvicorn.
# If run_server.py's uvicorn.run respects config.port (which reads $PORT), this is simpler:
CMD ["python", "src/python/run_server.py"]

# Alternative CMD using Gunicorn (as recommended for production-like environments)
# This requires Gunicorn to be in requirements.txt
# CMD ["gunicorn", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:${PORT}", "src.python.run_server:app_factory"]
# For the above Gunicorn command, run_server.py would need an app_factory() function
# that returns the FastAPI app instance, or point directly to the app if it's module-level.
# Given your current run_server.py, the python command is more direct.
# For "least effort PoC" with current run_server.py, the python CMD is fine.
