#!/bin/bash
# Cloud Run deployment script for Role Play System PoC
# This script builds, pushes, and deploys the Docker image to Google Cloud Run

set -e # Exit on any error

# ============================================================================
# CONFIGURATION - UPDATE THESE VALUES
# ============================================================================
PROJECT_ID="your-gcp-project-id" # MUST UPDATE: Replace with your actual GCP Project ID
SERVICE_NAME="rps-poc"
REGION="us-central1"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"
IMAGE_TAG="latest"
JWT_SECRET_NAME="jwt-rps-poc-secret" # Name of the secret in Google Secret Manager

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
print_header() {
    echo ""
    echo "============================================================"
    echo "$1"
    echo "============================================================"
}

check_prerequisites() {
    print_header "Checking prerequisites"
    
    # Check if gcloud is installed
    if ! command -v gcloud &> /dev/null; then
        echo "ERROR: gcloud CLI is not installed. Please install it first."
        echo "Visit: https://cloud.google.com/sdk/docs/install"
        exit 1
    fi
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        echo "ERROR: Docker is not installed. Please install it first."
        exit 1
    fi
    
    # Check if PROJECT_ID is updated
    if [ "$PROJECT_ID" == "your-gcp-project-id" ]; then
        echo "ERROR: Please update PROJECT_ID in this script with your actual GCP Project ID"
        exit 1
    fi
    
    echo "✓ Prerequisites checked"
}

# ============================================================================
# MAIN DEPLOYMENT PROCESS
# ============================================================================
check_prerequisites

print_header "Starting deployment for $SERVICE_NAME"
echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"
echo "Image: $IMAGE_NAME:$IMAGE_TAG"

# Build Docker image
print_header "Building Docker image"
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .

# Configure Docker authentication for GCR
print_header "Configuring Docker authentication"
gcloud auth configure-docker

# Push image to Google Container Registry
print_header "Pushing image to GCR"
docker push ${IMAGE_NAME}:${IMAGE_TAG}

# Check if JWT secret exists in Secret Manager
print_header "Checking JWT secret in Secret Manager"
if gcloud secrets describe ${JWT_SECRET_NAME} --project=${PROJECT_ID} &> /dev/null; then
    echo "✓ Secret '${JWT_SECRET_NAME}' exists"
else
    echo "WARNING: Secret '${JWT_SECRET_NAME}' does not exist in Secret Manager"
    echo ""
    echo "To create the secret, run:"
    echo "  python3 -c \"import secrets; print(secrets.token_urlsafe(32))\" > jwt-secret.txt"
    echo "  gcloud secrets create ${JWT_SECRET_NAME} --data-file=jwt-secret.txt --project=${PROJECT_ID}"
    echo "  rm jwt-secret.txt"
    echo ""
    echo "Then grant Cloud Run access to the secret:"
    echo "  PROJECT_NUMBER=\$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)')"
    echo "  gcloud secrets add-iam-policy-binding ${JWT_SECRET_NAME} \\"
    echo "    --member=\"serviceAccount:\${PROJECT_NUMBER}-compute@developer.gserviceaccount.com\" \\"
    echo "    --role=\"roles/secretmanager.secretAccessor\" \\"
    echo "    --project=${PROJECT_ID}"
    echo ""
    read -p "Press Enter to continue deployment without secret (NOT RECOMMENDED for production)..."
fi

# Deploy to Cloud Run
print_header "Deploying to Cloud Run"
gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE_NAME}:${IMAGE_TAG} \
  --platform managed \
  --region ${REGION} \
  --project ${PROJECT_ID} \
  --allow-unauthenticated \
  --port 8000 \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 2 \
  --set-env-vars "ENVIRONMENT=poc" \
  --set-env-vars "STORAGE_PATH=/tmp/data" \
  --set-env-vars "CORS_ORIGINS=https://poc.rps.cattail-sw.com" \
  --set-secrets "JWT_SECRET_KEY=${JWT_SECRET_NAME}:latest" \
  --timeout 60s \
  --concurrency 80 \
  --service-account "${PROJECT_ID}@appspot.gserviceaccount.com" \
  --ingress all \
  --set-startup-probe-path /health \
  --set-startup-probe-initial-delay 5s \
  --set-startup-probe-timeout 10s \
  --set-startup-probe-period 10s \
  --set-startup-probe-failure-threshold 3 \
  --set-liveness-probe-path /health \
  --set-liveness-probe-initial-delay 30s \
  --set-liveness-probe-timeout 10s \
  --set-liveness-probe-period 30s \
  --set-liveness-probe-failure-threshold 3

# Get the service URL
print_header "Deployment complete!"
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
  --platform managed \
  --region ${REGION} \
  --project ${PROJECT_ID} \
  --format 'value(status.url)')

echo "Service deployed successfully!"
echo "Service URL: ${SERVICE_URL}"
echo ""
echo "Next steps:"
echo "1. Test the health endpoint: curl ${SERVICE_URL}/health"
echo "2. Set up custom domain mapping in Cloud Run console"
echo "3. Update DNS records for poc.rps.cattail-sw.com"
echo ""
echo "To view logs:"
echo "  gcloud run logs read --service=${SERVICE_NAME} --region=${REGION} --project=${PROJECT_ID}"
echo ""
echo "To update CORS origins after getting the Cloud Run URL:"
echo "  gcloud run services update ${SERVICE_NAME} \\"
echo "    --update-env-vars \"CORS_ORIGINS=https://poc.rps.cattail-sw.com,${SERVICE_URL}\" \\"
echo "    --region=${REGION} --project=${PROJECT_ID}"
