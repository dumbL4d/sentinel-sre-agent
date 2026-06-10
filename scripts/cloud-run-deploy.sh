#!/usr/bin/env bash
set -euo pipefail

# Cloud Run deployment script for Sentinel SRE Agent
# Prerequisites:
#   1. gcloud CLI installed and authenticated
#   2. GEMINI_API_KEY stored in Secret Manager as "gemini-api-key"
#   3. Docker installed
#
# Usage:
#   export GCP_PROJECT_ID=my-project
#   bash scripts/cloud-run-deploy.sh

PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
REGION="us-central1"
SERVICE_NAME="sentinel-sre-agent"
ARTIFACT_REPO="${SERVICE_NAME}"
IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/${SERVICE_NAME}"

echo "==> Enabling required APIs..."
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com \
    --project="${PROJECT_ID}"

echo "==> Creating Artifact Registry repository..."
gcloud artifacts repositories create "${ARTIFACT_REPO}" \
    --repository-format=docker \
    --location="${REGION}" \
    --project="${PROJECT_ID}" || echo "Repository may already exist"

echo "==> Creating Secret for GEMINI_API_KEY..."
echo -n "your-gemini-api-key-here" | gcloud secrets create gemini-api-key \
    --data-file=- \
    --project="${PROJECT_ID}" 2>/dev/null || echo "Secret may already exist"

echo "==> Building and pushing image..."
gcloud builds submit \
    --tag "${IMAGE_NAME}:latest" \
    --project="${PROJECT_ID}"

echo "==> Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
    --image="${IMAGE_NAME}:latest" \
    --region="${REGION}" \
    --platform=managed \
    --allow-unauthenticated \
    --memory=2Gi \
    --cpu=2 \
    --min-instances=0 \
    --max-instances=10 \
    --timeout=300 \
    --concurrency=80 \
    --set-env-vars="SENTINEL_DEMO_MODE=true,GEMINI_MODEL=gemini-2.0-flash,PYTHONUNBUFFERED=1" \
    --set-secrets="GEMINI_API_KEY=gemini-api-key:latest" \
    --project="${PROJECT_ID}"

echo "==> Getting service URL..."
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --format='value(status.url)')

echo ""
echo "==========================================="
echo "  Deployed to: ${SERVICE_URL}"
echo "  Web UI:      ${SERVICE_URL}/ui/"
echo "  Health:      ${SERVICE_URL}/health"
echo "  API Docs:    ${SERVICE_URL}/docs"
echo "==========================================="
