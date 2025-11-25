#!/bin/bash

# Deployment script for Cloud Run
# Usage: ./scripts/deploy.sh [environment]

set -e

# Configuration
ENVIRONMENT=${1:-production}
PROJECT_ID=${GCP_PROJECT_ID:-"your-project-id"}
SERVICE_NAME="data-analysis-service"
REGION=${GCP_REGION:-"us-central1"}
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🚀 Deploying to Cloud Run..."
echo "Environment: ${ENVIRONMENT}"
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"

# Build the container image
echo "📦 Building container image..."
gcloud builds submit --tag ${IMAGE_NAME} --project ${PROJECT_ID}

# Deploy to Cloud Run
echo "🌐 Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME} \
    --platform managed \
    --region ${REGION} \
    --project ${PROJECT_ID} \
    --allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --timeout 3600 \
    --max-instances 10 \
    --min-instances 0 \
    --set-env-vars "ENVIRONMENT=${ENVIRONMENT},GCP_PROJECT_ID=${PROJECT_ID},WORKFLOW_NAME=daily_data_analysis"

# Get the service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --platform managed \
    --region ${REGION} \
    --project ${PROJECT_ID} \
    --format 'value(status.url)')

echo "✅ Deployment completed!"
echo "Service URL: ${SERVICE_URL}"
echo ""
echo "Test endpoints:"
echo "  Health: ${SERVICE_URL}/health"
echo "  Status: ${SERVICE_URL}/status"
echo "  Run Analysis: ${SERVICE_URL}/run-analysis"
