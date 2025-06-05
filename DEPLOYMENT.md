# Role Play System - Google Cloud Deployment Guide

This guide covers deploying the Role Play System to Google Cloud Platform (GCP) for beta and production environments.

## Prerequisites

1. **Google Cloud Project** with billing enabled
2. **gcloud CLI** installed and authenticated
3. **Docker** installed locally
4. **Node.js 18+** for frontend build
5. **Make** command available (for automation)
6. **Git** for version tagging

## Quick Start with Makefile

The project includes a comprehensive Makefile that automates most deployment tasks. For most use cases, you should use these commands instead of manual deployment.

### View Available Commands
```bash
make help
```

### Deploy to Environment
```bash
# Deploy to beta
make deploy ENV=beta

# Deploy to production
make deploy ENV=prod

# Deploy a specific image tag
make deploy-image ENV=prod IMAGE_TAG=v1.2.3
```

### Local Development
```bash
# Run locally with Docker
make run-local-docker

# Build Docker image only
make build-docker
```

## Configuration Setup

### 1. Create `.env.mk` File

First, create a `.env.mk` file (git-ignored) with your GCP project IDs:

```bash
# .env.mk
GCP_PROJECT_ID_PROD=your-actual-prod-project-id
GCP_PROJECT_ID_BETA=your-actual-beta-project-id
GCP_PROJECT_ID_DEV=your-actual-dev-project-id
```

### 2. Set Up GCP Infrastructure

The Makefile can automatically create most GCP resources:

```bash
# Set up beta environment
make setup-gcp-infra ENV=beta

# Set up production environment
make setup-gcp-infra ENV=prod
```

This will attempt to:
- Enable required APIs (Cloud Run, Artifact Registry, Secret Manager, etc.)
- Create GCS buckets for app data and log exports
- Create Artifact Registry repository
- Create service account
- Create Secret Manager container for JWT key

**Note**: You still need to manually add the JWT secret value:

```bash
# Generate a secure secret
echo -n "$(openssl rand -base64 32)" | gcloud secrets versions add rps-jwt-secret \
    --data-file=- \
    --project=YOUR_PROJECT_ID
```

## Architecture Overview

The deployment uses:
- **Cloud Run** for the containerized FastAPI + Vue.js application
- **Google Cloud Storage (GCS)** for data persistence
- **Artifact Registry** for Docker images
- **Secret Manager** for sensitive configuration
- **Cloud Logging** for centralized logs
- **Service Accounts** for secure access

## Docker Configuration

The project uses a multi-stage Dockerfile that:
1. Builds the Vue.js frontend
2. Sets up the Python backend
3. Serves the frontend as static files

To build locally:
```bash
make build-docker
```

## Deployment Process

### Standard Deployment Flow

1. **Ensure configuration is set**:
   ```bash
   make list-config ENV=beta
   ```

2. **Build and deploy**:
   ```bash
   make deploy ENV=beta
   ```

   This will:
   - Build the Docker image with current git version
   - Push to Artifact Registry
   - Deploy to Cloud Run with appropriate settings

### Manual Deployment (Advanced)

If you need to deploy manually, the Makefile executes commands similar to:

```bash
# Build
docker build -t {region}-docker.pkg.dev/{project}/rps-images/rps-api:{tag} .

# Push
docker push {region}-docker.pkg.dev/{project}/rps-images/rps-api:{tag}

# Deploy
gcloud run deploy rps-api-{env} \
    --image={image} \
    --region=us-central1 \
    --set-env-vars="ENV={env},GCS_BUCKET={bucket},..." \
    --set-secrets="JWT_SECRET_KEY={secret-name}:latest" \
    --service-account={service-account} \
    ...
```

## Environment Variables

The Makefile automatically sets these environment variables based on ENV:

| Variable | Description | Makefile Sets |
|----------|-------------|---------------|
| `ENV` | Environment name | ✓ |
| `CONFIG_FILE` | Path to config file | ✓ |
| `GCP_PROJECT_ID` | Google Cloud project ID | ✓ |
| `GCS_BUCKET` | Storage bucket name | ✓ |
| `GCS_PREFIX` | Storage prefix | ✓ |
| `LOG_LEVEL` | Logging level | ✓ |
| `CORS_ALLOWED_ORIGINS` | CORS origins | ✓ |
| `JWT_SECRET_KEY` | From Secret Manager | ✓ |

## Storage Configuration

Each environment uses different GCS buckets:
- **Dev**: `rps-app-data-dev` with prefix `dev/`
- **Beta**: `rps-app-data-beta` with prefix `beta/`
- **Prod**: `rps-app-data-prod` with prefix `prod/`

Log exports (optional) go to separate buckets:
- **Dev**: `rps-log-exports-dev`
- **Beta**: `rps-log-exports-beta`
- **Prod**: `rps-log-exports-prod`

## Monitoring and Logging

### View Logs
```bash
# Using Makefile
make logs ENV=beta

# Or manually
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=rps-api-beta" \
    --limit=50 --project=YOUR_PROJECT_ID
```

### Health Checks

The application exposes:
- `/health` - Basic health check
- `/api/v1/*` - API endpoints

## Version Management

### Tag a Release
```bash
make tag-git-release NEW_GIT_TAG=v1.2.3
```

### Deploy Specific Version
```bash
make deploy-image ENV=prod IMAGE_TAG=v1.2.3
```

## Troubleshooting

### Common Issues

1. **GCP Project ID not set**
   - Create `.env.mk` with your project IDs
   - Or export them: `export GCP_PROJECT_ID_BETA=your-project`

2. **Permission Denied**
   - Ensure you're authenticated: `gcloud auth login`
   - Check service account permissions

3. **Build Failures**
   - Check Node.js version for frontend build
   - Ensure all dependencies are installed

4. **Secret Not Found**
   - Create JWT secret in Secret Manager
   - Grant service account access to secret

### Debug Commands

```bash
# Check current configuration
make list-config ENV=beta

# Test locally before deploying
make run-local-docker

# View service details
gcloud run services describe rps-api-beta --region=us-central1
```

## CI/CD with Cloud Build

For automated deployments, create a Cloud Build trigger:

### cloudbuild.yaml
```yaml
steps:
  # Build the container image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'us-central1-docker.pkg.dev/$PROJECT_ID/rps-images/rps-api:$COMMIT_SHA', '.']
  
  # Push to Artifact Registry
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'us-central1-docker.pkg.dev/$PROJECT_ID/rps-images/rps-api:$COMMIT_SHA']
  
  # Deploy to beta (only on main branch)
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: make
    args: ['deploy-image', 'ENV=beta', 'IMAGE_TAG=$COMMIT_SHA']
    env:
      - 'GCP_PROJECT_ID_BETA=$PROJECT_ID'

images:
  - 'us-central1-docker.pkg.dev/$PROJECT_ID/rps-images/rps-api:$COMMIT_SHA'

options:
  logging: CLOUD_LOGGING_ONLY
```

## Cost Optimization

The Makefile sets appropriate defaults:
- **Dev/Beta**: 0 minimum instances (allows cold starts)
- **Prod**: 1 minimum instance (avoids cold starts)
- **Concurrency**: 80 requests per instance
- **Auto-scaling**: 10 max instances (beta), 100 max (prod)

## Security Best Practices

1. **Use `.env.mk` for project IDs only** - never commit secrets
2. **JWT secrets in Secret Manager** - rotated regularly
3. **Separate service accounts** per environment
4. **Least privilege access** - only required permissions

## Manual GCP Setup Reference

If `make setup-gcp-infra` fails, manually create resources:

### Enable APIs
```bash
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com \
    storage.googleapis.com \
    --project=YOUR_PROJECT_ID
```

### Create Resources
```bash
# Artifact Registry
gcloud artifacts repositories create rps-images \
    --repository-format=docker \
    --location=us-central1 \
    --project=YOUR_PROJECT_ID

# Service Account
gcloud iam service-accounts create sa-rps \
    --display-name="RPS Application Service Account" \
    --project=YOUR_PROJECT_ID

# GCS Buckets
gsutil mb -p YOUR_PROJECT_ID -l us-central1 gs://rps-app-data-{env}/
gsutil mb -p YOUR_PROJECT_ID -l us-central1 gs://rps-log-exports-{env}/

# Grant permissions
gsutil iam ch serviceAccount:sa-rps@YOUR_PROJECT_ID.iam.gserviceaccount.com:objectAdmin \
    gs://rps-app-data-{env}/
```

## Next Steps

1. Set up `.env.mk` with your GCP project IDs
2. Run `make setup-gcp-infra ENV=beta` to create infrastructure
3. Add JWT secret to Secret Manager
4. Deploy with `make deploy ENV=beta`
5. Set up monitoring dashboards in Cloud Console
6. Configure alerting for critical metrics