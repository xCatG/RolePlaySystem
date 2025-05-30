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

## Production Architecture

### Overview

The production deployment evolves from the single-container POC to a scalable, resilient microservices architecture:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Nginx     │────▶│  Frontend   │────▶│ Static CDN  │
│  (SSL/LB)   │     │  (Vue.js)   │     │   (Assets)  │
└─────────────┘     └─────────────┘     └─────────────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  API Gateway│────▶│Auth Service │────▶│  Redis      │
│  (Kong/AWS) │     │  (FastAPI)  │     │  (Sessions) │
└─────────────┘     └─────────────┘     └─────────────┘
       │
       ├────────────▶┌─────────────┐     ┌─────────────┐
       │             │Chat Service │────▶│  PostgreSQL │
       │             │  (FastAPI)  │     │  (Metadata) │
       │             └─────────────┘     └─────────────┘
       │                    │
       │                    ▼
       │             ┌─────────────┐     ┌─────────────┐
       └────────────▶│ Eval Service│────▶│  S3/GCS     │
                     │  (FastAPI)  │     │  (Logs)     │
                     └─────────────┘     └─────────────┘
```

### Docker Compose Production Setup

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  frontend:
    image: rps-frontend:${VERSION:-latest}
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - backend
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    restart: unless-stopped
    
  backend:
    image: rps-backend:${VERSION:-latest}
    environment:
      - DATABASE_URL=postgresql://rps:${DB_PASSWORD}@postgres:5432/rps
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
      - S3_BUCKET=${S3_BUCKET}
      - ENVIRONMENT=prod
    depends_on:
      - postgres
      - redis
    deploy:
      replicas: 3
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    
  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=rps
      - POSTGRES_USER=rps
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
      
  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

### Kubernetes Deployment

```yaml
# k8s/deployment.yml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rps-backend
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: rps-backend
  template:
    metadata:
      labels:
        app: rps-backend
    spec:
      containers:
      - name: backend
        image: registry.example.com/rps-backend:v1.0.0
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: rps-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: rps-secrets
              key: redis-url
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: rps-backend
  namespace: production
spec:
  selector:
    app: rps-backend
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: rps-backend-hpa
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: rps-backend
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Migration Path from POC to Production

#### Phase 1: Database Migration (2-3 weeks)
1. **Design Schema**
   ```sql
   -- Users table
   CREATE TABLE users (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     username VARCHAR(50) UNIQUE NOT NULL,
     email VARCHAR(255) UNIQUE NOT NULL,
     role VARCHAR(20) NOT NULL DEFAULT 'USER',
     created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
     updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
   );
   
   -- Sessions table
   CREATE TABLE chat_sessions (
     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
     user_id UUID REFERENCES users(id),
     scenario_id VARCHAR(50) NOT NULL,
     character_id VARCHAR(50) NOT NULL,
     created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
     ended_at TIMESTAMP WITH TIME ZONE,
     log_file_path VARCHAR(500)
   );
   ```

2. **Implement Database Models**
   - SQLAlchemy models for all entities
   - Alembic for migration management
   - Connection pooling configuration

3. **Create Migration Scripts**
   - Export FileStorage data to SQL
   - Verify data integrity
   - Performance testing

#### Phase 2: Service Separation (3-4 weeks)
1. **Extract Services**
   - Auth Service: User management, JWT, OAuth
   - Chat Service: Session management, ADK integration
   - Evaluation Service: Export, analytics

2. **API Gateway Setup**
   - Kong or AWS API Gateway
   - Rate limiting per service
   - Request routing rules

3. **Inter-Service Communication**
   - gRPC for internal services
   - Message queue for async tasks
   - Service discovery

#### Phase 3: Infrastructure (2-3 weeks)
1. **Kubernetes Setup**
   - EKS/GKE/AKS cluster provisioning
   - Namespace configuration
   - RBAC policies

2. **CI/CD Pipeline**
   ```yaml
   # .github/workflows/deploy.yml
   name: Deploy to Production
   on:
     push:
       tags:
         - 'v*'
   jobs:
     test:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v3
         - name: Run tests
           run: |
             make test
             make integration-test
     
     build:
       needs: test
       runs-on: ubuntu-latest
       steps:
         - uses: docker/build-push-action@v4
           with:
             push: true
             tags: |
               ${{ secrets.REGISTRY }}/rps-backend:${{ github.ref_name }}
               ${{ secrets.REGISTRY }}/rps-backend:latest
     
     deploy:
       needs: build
       runs-on: ubuntu-latest
       steps:
         - name: Deploy to Kubernetes
           run: |
             kubectl set image deployment/rps-backend \
               backend=${{ secrets.REGISTRY }}/rps-backend:${{ github.ref_name }} \
               -n production
             kubectl rollout status deployment/rps-backend -n production
   ```

3. **Monitoring Stack**
   - Prometheus for metrics
   - Grafana for visualization
   - Loki for log aggregation
   - Jaeger for distributed tracing

#### Phase 4: Security & Performance (2-3 weeks)
1. **Security Hardening**
   - HashiCorp Vault for secrets
   - mTLS between services
   - WAF configuration
   - Penetration testing

2. **Performance Optimization**
   - Redis caching layer
   - Database query optimization
   - CDN for static assets
   - Load testing (target: 10k concurrent users)

3. **Disaster Recovery**
   - Multi-region deployment
   - Automated backups
   - Failover testing
   - RTO/RPO documentation

### Production Environment Variables

```env
# .env.prod
# Database
DATABASE_URL=postgresql://rps:password@postgres:5432/rps
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40

# Redis
REDIS_URL=redis://:password@redis:6379
REDIS_MAX_CONNECTIONS=50

# S3/GCS Storage
S3_BUCKET=rps-production-logs
S3_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# Security
JWT_SECRET_KEY=<generate-strong-key>
JWT_ALGORITHM=RS256
JWT_PUBLIC_KEY_PATH=/secrets/jwt-public.pem
JWT_PRIVATE_KEY_PATH=/secrets/jwt-private.pem

# API Rate Limiting
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000

# Monitoring
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_SERVICE_NAME=rps-backend
OTEL_METRICS_EXPORTER=prometheus

# Feature Flags
ENABLE_WEBSOCKET_CHAT=true
ENABLE_OAUTH_LOGIN=true
ENABLE_EVALUATION_ANALYTICS=true
```

### Production Checklist (Extended)

#### Infrastructure
- [ ] Multi-region Kubernetes clusters
- [ ] Auto-scaling policies configured
- [ ] Load balancer with health checks
- [ ] CDN for static assets
- [ ] Database replication (primary + read replicas)
- [ ] Redis cluster mode enabled
- [ ] S3 lifecycle policies for log rotation
- [ ] Backup and restore procedures tested

#### Security
- [ ] TLS 1.3 everywhere
- [ ] API Gateway with rate limiting
- [ ] WAF rules configured
- [ ] Secrets rotation policy
- [ ] Security scanning in CI/CD
- [ ] Penetration test passed
- [ ] OWASP Top 10 addressed
- [ ] Data encryption at rest

#### Monitoring
- [ ] Application metrics dashboard
- [ ] Infrastructure metrics dashboard
- [ ] Log aggregation and search
- [ ] Distributed tracing enabled
- [ ] Alerting rules configured
- [ ] On-call rotation setup
- [ ] Runbooks documented
- [ ] SLIs/SLOs defined

#### Performance
- [ ] Load tested to 10k concurrent users
- [ ] P95 latency < 200ms
- [ ] Database queries optimized (< 50ms)
- [ ] Redis cache hit rate > 90%
- [ ] CDN cache hit rate > 80%
- [ ] Image optimization applied
- [ ] Response compression enabled
- [ ] Connection pooling tuned

## Support

For additional help:
- Check the logs first: `docker logs rps-app`
- Review the health endpoint: `curl http://localhost:8000/health`
- Ensure all environment variables are set correctly
- Verify the data volume is properly mounted
- For production issues, check the monitoring dashboards and distributed traces