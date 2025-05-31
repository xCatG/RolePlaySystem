# Role Play System - Google Cloud Deployment Guide

This guide covers deploying the Role Play System to Google Cloud Platform (GCP) for beta and production environments.

## Prerequisites

1. **Google Cloud Project** with billing enabled
2. **gcloud CLI** installed and authenticated
3. **Docker** installed locally
4. **Service Account** with appropriate permissions
5. **Google Cloud Storage buckets** created for each environment

## Architecture Overview

The deployment uses:
- **Cloud Run** for the containerized FastAPI application
- **Google Cloud Storage (GCS)** for data persistence
- **Cloud Build** for CI/CD
- **Secret Manager** for sensitive configuration
- **Cloud Logging** for centralized logs
- **Application Default Credentials (ADC)** for authentication

## Environment Setup

### 1. Create GCS Buckets

```bash
# Beta environment
gsutil mb -p YOUR_PROJECT_ID -c STANDARD -l us-central1 gs://roleplay-beta-storage/

# Production environment
gsutil mb -p YOUR_PROJECT_ID -c STANDARD -l us-central1 gs://roleplay-prod-storage/
```

### 2. Set up Secret Manager

```bash
# Create JWT secret
echo -n "your-secure-jwt-secret-here" | gcloud secrets create jwt-secret-key \
    --data-file=- \
    --replication-policy="automatic"

# Grant Cloud Run access to the secret
gcloud secrets add-iam-policy-binding jwt-secret-key \
    --member="serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

### 3. Create Service Account (if not using default)

```bash
# Create service account
gcloud iam service-accounts create roleplay-service \
    --display-name="Role Play Service Account"

# Grant necessary permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:roleplay-service@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:roleplay-service@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/logging.logWriter"
```

## Docker Configuration

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY src/python/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/python/ ./src/python/
COPY data/ ./data/
COPY config/ ./config/

# Set Python path
ENV PYTHONPATH=/app/src/python

# Run the application
CMD ["python", "src/python/run_server.py"]
```

### .dockerignore

```
.git/
.gitignore
*.pyc
__pycache__/
.pytest_cache/
.coverage
htmlcov/
venv/
.env
.env.local
*.log
test/
docs/
README.md
DEPLOYMENT.md
```

## Build and Deploy

### 1. Build Container Image

```bash
# Build locally
docker build -t gcr.io/YOUR_PROJECT_ID/roleplay-api:latest .

# Or use Cloud Build
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/roleplay-api:latest .
```

### 2. Deploy to Cloud Run

#### Beta Deployment

```bash
gcloud run deploy roleplay-api-beta \
    --image gcr.io/YOUR_PROJECT_ID/roleplay-api:latest \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --set-env-vars="ENV=beta" \
    --set-env-vars="CONFIG_FILE=/app/config/beta.yaml" \
    --set-env-vars="GCP_PROJECT_ID=YOUR_PROJECT_ID" \
    --set-env-vars="GCS_BUCKET=roleplay-beta-storage" \
    --set-env-vars="GCS_PREFIX=beta/" \
    --set-env-vars="FRONTEND_URL=https://beta-roleplay.example.com" \
    --set-secrets="JWT_SECRET_KEY=jwt-secret-key:latest" \
    --service-account=roleplay-service@YOUR_PROJECT_ID.iam.gserviceaccount.com \
    --memory=1Gi \
    --cpu=1 \
    --min-instances=1 \
    --max-instances=10 \
    --concurrency=100
```

#### Production Deployment

```bash
gcloud run deploy roleplay-api-prod \
    --image gcr.io/YOUR_PROJECT_ID/roleplay-api:latest \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --set-env-vars="ENV=prod" \
    --set-env-vars="CONFIG_FILE=/app/config/prod.yaml" \
    --set-env-vars="GCP_PROJECT_ID=YOUR_PROJECT_ID" \
    --set-env-vars="GCS_BUCKET=roleplay-prod-storage" \
    --set-env-vars="GCS_PREFIX=prod/" \
    --set-env-vars="FRONTEND_URL=https://roleplay.example.com" \
    --set-env-vars="LOG_LEVEL=WARNING" \
    --set-secrets="JWT_SECRET_KEY=jwt-secret-key:latest" \
    --service-account=roleplay-service@YOUR_PROJECT_ID.iam.gserviceaccount.com \
    --memory=2Gi \
    --cpu=2 \
    --min-instances=2 \
    --max-instances=100 \
    --concurrency=200
```

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `ENV` | Environment name | `beta` or `prod` |
| `CONFIG_FILE` | Path to config file | `/app/config/beta.yaml` |
| `GCP_PROJECT_ID` | Google Cloud project ID | `my-project-123` |
| `JWT_SECRET_KEY` | Secret for JWT signing | (use Secret Manager) |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GCS_BUCKET` | Storage bucket name | `roleplay-{env}-storage` |
| `GCS_PREFIX` | Storage prefix | `{env}/` |
| `FRONTEND_URL` | Frontend URL for CORS | Environment specific |
| `LOG_LEVEL` | Logging level | `INFO` (beta), `WARNING` (prod) |
| `JWT_EXPIRE_HOURS` | JWT token expiration | `72` (beta), `168` (prod) |
| `LOCK_LEASE_DURATION` | Lock duration in seconds | `45` (beta), `30` (prod) |

## CI/CD with Cloud Build

### cloudbuild.yaml

```yaml
steps:
  # Build the container image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/roleplay-api:$COMMIT_SHA', '.']
  
  # Push to Container Registry
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/roleplay-api:$COMMIT_SHA']
  
  # Deploy to beta (only on main branch)
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - 'roleplay-api-beta'
      - '--image=gcr.io/$PROJECT_ID/roleplay-api:$COMMIT_SHA'
      - '--region=us-central1'
      - '--platform=managed'
    condition: '$BRANCH_NAME == "main"'

# Store image in Artifact Registry
images:
  - 'gcr.io/$PROJECT_ID/roleplay-api:$COMMIT_SHA'

options:
  logging: CLOUD_LOGGING_ONLY
```

### Set up Build Trigger

```bash
gcloud builds triggers create cloud-source-repositories \
    --repo=roleplay-system \
    --branch-pattern="^main$" \
    --build-config=cloudbuild.yaml \
    --description="Deploy to beta on push to main"
```

## Monitoring and Logging

### View Logs

```bash
# Beta logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=roleplay-api-beta" \
    --limit 50 \
    --format json

# Production logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=roleplay-api-prod" \
    --limit 50 \
    --format json
```

### Set up Alerts

```bash
# Create alert policy for high error rate
gcloud alpha monitoring policies create \
    --notification-channels=YOUR_CHANNEL_ID \
    --display-name="High Error Rate - Role Play API" \
    --condition-display-name="Error rate > 1%" \
    --condition-filter='resource.type="cloud_run_revision" AND metric.type="run.googleapis.com/request_count" AND metric.label.response_code_class="5xx"'
```

## Health Checks

The application exposes health check endpoints:

- `/health` - Basic health check
- `/metrics` - Prometheus-compatible metrics (when enabled)

Cloud Run automatically uses these for traffic routing and autoscaling.

## Troubleshooting

### Common Issues

1. **Storage Access Denied**
   - Verify service account has `roles/storage.objectAdmin` on the bucket
   - Check bucket exists and is in the correct project

2. **JWT Secret Not Found**
   - Ensure secret exists in Secret Manager
   - Verify service account has access to the secret

3. **High Latency**
   - Check lock contention metrics
   - Consider migrating to Redis locking if object locks are slow
   - Review Cloud Run concurrency settings

4. **Memory Issues**
   - Increase memory allocation in Cloud Run
   - Check for memory leaks in long-running connections

### Debug Commands

```bash
# Check service status
gcloud run services describe roleplay-api-beta --region=us-central1

# View recent logs
gcloud run services logs read roleplay-api-beta --region=us-central1

# Test endpoint
curl https://roleplay-api-beta-xxxxx-uc.a.run.app/health

# Check storage bucket
gsutil ls -la gs://roleplay-beta-storage/
```

## Rollback Procedure

```bash
# List revisions
gcloud run revisions list --service=roleplay-api-prod --region=us-central1

# Rollback to previous revision
gcloud run services update-traffic roleplay-api-prod \
    --region=us-central1 \
    --to-revisions=roleplay-api-prod-00001-abc=100
```

## Cost Optimization

1. **Set minimum instances appropriately**
   - Beta: 1 instance (accept cold starts)
   - Production: 2+ instances (avoid cold starts)

2. **Use appropriate CPU/memory allocation**
   - Start small and scale based on metrics
   - Monitor CPU and memory usage

3. **Configure autoscaling**
   - Set reasonable max instances
   - Adjust concurrency based on load testing

4. **Storage costs**
   - Implement lifecycle policies for old chat logs
   - Consider archival storage for historical data

## Security Best Practices

1. **Never commit secrets**
   - Use Secret Manager for all sensitive data
   - Rotate JWT secrets regularly

2. **Least privilege access**
   - Service accounts should have minimal required permissions
   - Use separate service accounts for different environments

3. **Network security**
   - Consider using Cloud Armor for DDoS protection
   - Implement rate limiting in production

4. **Regular updates**
   - Keep dependencies updated
   - Monitor security advisories

## Next Steps

1. **Set up monitoring dashboards** in Cloud Console
2. **Configure alerting** for critical metrics
3. **Implement automated testing** before deployment
4. **Set up staging environment** for pre-production testing
5. **Document runbooks** for common operational tasks