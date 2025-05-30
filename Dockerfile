# Stage 1: Build Vue.js Frontend
FROM node:18-alpine AS frontend-builder

# Set working directory for frontend
WORKDIR /app/frontend

# Copy package.json and package-lock.json
COPY src/ts/role_play/ui/package.json src/ts/role_play/ui/package-lock.json* ./

# Install frontend dependencies
RUN npm install

# Copy the rest of the frontend source code
COPY src/ts/role_play/ui/ ./

# Build the frontend application
RUN npm run build

# Stage 2: Build Python Backend and Serve Frontend
FROM python:3.12-slim-bookworm AS backend

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory for backend
WORKDIR /app/backend

# Copy Python requirements file
COPY src/python/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the entire Python application code
COPY src/python/ ./src/python/
COPY config/ ./config/

# Copy the scenarios.json file to a location that won't be overridden by volume mount
COPY data/scenarios.json ./static_data/scenarios.json

# Copy the built frontend assets from the frontend-builder stage
COPY --from=frontend-builder /app/frontend/dist ./static_frontend

# Expose the port the app runs on
EXPOSE 8000

# Command to run the Uvicorn server
CMD ["python", "src/python/run_server.py"]