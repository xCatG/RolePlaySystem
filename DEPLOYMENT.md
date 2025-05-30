# Role Play System - Deployment Guide

## Table of Contents
- [Docker Deployment](#docker-deployment)
- [Environment Configuration](#environment-configuration)
- [Common Issues & Debugging](#common-issues--debugging)
- [Production Checklist](#production-checklist)

## Docker Deployment

### Prerequisites
- Docker installed on your system
- Docker Compose (optional, for multi-container setup)
- At least 2GB of free disk space

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd rps
   ```

2. **Create environment file**
   ```bash
   # Generate a secure JWT secret
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   
   # Create .env.prod with the generated secret
   cp .env.example .env.prod
   # Edit .env.prod and set JWT_SECRET_KEY with the generated value
   ```

3. **Build and run with Make**
   ```bash
   make run
   ```

4. **Access the application**
   - Open http://localhost:8000 in your browser
   - Register a new account or login

### Manual Docker Commands

If you prefer not to use Make:

```bash
# Build the image
docker build -t role-play-system:latest .

# Run the container
docker run -d \
  --name rps-app \
  -p 8000:8000 \
  -v "$(pwd)/rps_data_volume:/app/backend/data" \
  --env-file .env.prod \
  role-play-system:latest
```

### Makefile Commands

- `make build` - Build the Docker image
- `make run` - Build and run the container
- `make stop` - Stop and remove the container
- `make logs` - View container logs
- `make clean` - Remove container and image

## Environment Configuration

### Required Environment Variables

Create a `.env.prod` file with these variables:

```env
# REQUIRED: JWT Secret Key for token signing
JWT_SECRET_KEY=<generate-with-python-command-above>

# Environment (dev, beta, prod)
ENVIRONMENT=dev

# Storage path (inside container)
STORAGE_PATH=/app/backend/data

# Google AI SDK Configuration (if using chat features)
GOOGLE_API_KEY=your-api-key
GOOGLE_CLOUD_PROJECT=your-project
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_GENAI_USE_VERTEXAI=FALSE
ADK_MODEL=gemini-2.0-flash
```

### Optional Environment Variables

```env
# API Keys for chat functionality
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key

# OAuth Configuration
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Server Configuration
HOST=0.0.0.0
PORT=8000
JWT_EXPIRE_HOURS=24
```

## Common Issues & Debugging

### 1. Viewing Docker Logs

```bash
# Real-time logs
docker logs -f rps-app

# Last 100 lines
docker logs --tail 100 rps-app

# Logs with timestamps
docker logs -t rps-app

# Search for errors
docker logs rps-app 2>&1 | grep -i error
```

### 2. Scenario Picker Not Working

**Symptoms**: After login, the scenario dropdown is empty or not showing

**Common Causes & Solutions**:

1. **Missing scenarios.json file**
   ```bash
   # Check if file exists in container
   docker exec rps-app ls -la /app/backend/static_data/
   
   # Should show: scenarios.json
   ```

2. **Route ordering issue (API returns HTML instead of JSON)**
   ```bash
   # Test the API endpoint
   TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email": "test@example.com", "password": "testpass123"}' \
     | jq -r '.access_token')
   
   curl -s http://localhost:8000/chat/content/scenarios \
     -H "Authorization: Bearer $TOKEN" | jq
   ```
   
   If this returns HTML, the catch-all route is overriding API routes.

3. **Missing JWT_SECRET_KEY**
   ```bash
   # Check if environment variable is set
   docker exec rps-app printenv | grep JWT_SECRET_KEY
   
   # If missing, ensure .env.prod exists and container was started with --env-file
   ```

### 3. Authentication Issues

**500 Internal Server Error on login/register**:

1. **Check JWT_SECRET_KEY is set**
   ```bash
   # Must not be the default "your-secret-key-here"
   docker exec rps-app printenv | grep JWT_SECRET_KEY
   ```

2. **Verify user registration format**
   ```bash
   # Registration requires username, email, and password
   curl -X POST http://localhost:8000/auth/register \
     -H "Content-Type: application/json" \
     -d '{
       "username": "testuser",
       "email": "test@example.com", 
       "password": "testpass123"
     }'
   ```

### 4. Chrome Extension Interference

**Symptoms**: Browser becomes slow, DevTools shows "100000 hidden" messages

**Solution**: 
- Disable browser extensions (especially image/screenshot tools)
- Use incognito mode
- Try a different browser

**Console spam pattern**:
```
[CORS] Retrying image with anonymous crossOrigin: http://localhost:8000/favicon.ico...
[CORS] Final fallback attempt with no crossorigin: http://localhost:8000/favicon.ico...
```

### 5. Container Debugging

```bash
# Access container shell
docker exec -it rps-app /bin/bash

# Check running processes
docker exec rps-app ps aux

# View file structure
docker exec rps-app find /app -name "*.json"

# Test internal endpoints
docker exec rps-app curl -s http://localhost:8000/health | python3 -m json.tool
```

### 6. Volume Mount Issues

The Docker setup uses a volume mount for persistent data storage:
- Host: `./rps_data_volume/`
- Container: `/app/backend/data/`

**Important**: This volume mount can override files in the container's `/app/backend/data/` directory. Static data files like `scenarios.json` are stored in `/app/backend/static_data/` to avoid this issue.

### 7. Health Check Endpoint

Test system health:
```bash
curl http://localhost:8000/health | jq
```

Expected response:
```json
{
  "status": "healthy",
  "version": "1.0.0-dev",
  "checks": {
    "scenarios": {
      "status": "ok",
      "count": 2,
      "data_file": "/app/backend/static_data/scenarios.json"
    },
    "storage": {
      "status": "ok",
      "path": "/app/backend/data"
    }
  }
}
```

## Production Checklist

### Security
- [ ] Generate strong JWT_SECRET_KEY (never use default)
- [ ] Set ENVIRONMENT=prod
- [ ] Configure HTTPS/TLS termination
- [ ] Set secure CORS origins (not wildcards)
- [ ] Review and restrict API rate limits
- [ ] Enable request logging and monitoring

### Configuration
- [ ] Use production database (when implemented)
- [ ] Configure proper backup strategy
- [ ] Set appropriate resource limits in Docker
- [ ] Configure health checks and auto-restart
- [ ] Set up log rotation

### Deployment
- [ ] Use Docker Compose or Kubernetes for orchestration
- [ ] Configure load balancer for multiple instances
- [ ] Set up monitoring and alerting
- [ ] Document rollback procedures
- [ ] Test disaster recovery plan

### Performance
- [ ] Enable response caching where appropriate
- [ ] Configure CDN for static assets
- [ ] Optimize Docker image size
- [ ] Set appropriate worker/thread counts
- [ ] Monitor and tune resource usage

## Troubleshooting Flowchart

```
Application not working?
├── Can you access http://localhost:8000?
│   ├── No → Check if container is running: docker ps
│   │         └── Not running → Check logs: docker logs rps-app
│   └── Yes → Can you login/register?
│       ├── No → Check JWT_SECRET_KEY is set
│       │         └── Check .env.prod exists and is used
│       └── Yes → Are scenarios loading?
│           ├── No → Check /health endpoint
│           │         └── Check scenarios.json location
│           └── Yes → System is working!
```

## Support

For additional help:
- Check the logs first: `docker logs rps-app`
- Review the health endpoint: `curl http://localhost:8000/health`
- Ensure all environment variables are set correctly
- Verify the data volume is properly mounted