#!/bin/bash

# Setup Cloud Scheduler for daily cron job
# Usage: ./scripts/setup-scheduler.sh

set -e

# Configuration
PROJECT_ID=${GCP_PROJECT_ID:-"your-project-id"}
REGION=${GCP_REGION:-"us-central1"}
SERVICE_NAME="data-analysis-service"
JOB_NAME="daily-data-analysis-job"
SCHEDULE="0 3 * * *"  # 3 AM daily

echo "⏰ Setting up Cloud Scheduler..."

# Get the Cloud Run service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --platform managed \
    --region ${REGION} \
    --project ${PROJECT_ID} \
    --format 'value(status.url)')

if [ -z "$SERVICE_URL" ]; then
    echo "❌ Error: Could not find Cloud Run service. Deploy the service first."
    exit 1
fi

echo "Service URL: ${SERVICE_URL}"
echo "Schedule: ${SCHEDULE}"

# Check if job exists
if gcloud scheduler jobs describe ${JOB_NAME} --location=${REGION} --project=${PROJECT_ID} &> /dev/null; then
    echo "Updating existing job..."
    
    gcloud scheduler jobs update http ${JOB_NAME} \
        --location=${REGION} \
        --project=${PROJECT_ID} \
        --schedule="${SCHEDULE}" \
        --uri="${SERVICE_URL}/run-analysis" \
        --http-method=POST \
        --oidc-service-account-email=${SERVICE_NAME}@${PROJECT_ID}.iam.gserviceaccount.com
else
    echo "Creating new job..."
    
    gcloud scheduler jobs create http ${JOB_NAME} \
        --location=${REGION} \
        --project=${PROJECT_ID} \
        --schedule="${SCHEDULE}" \
        --uri="${SERVICE_URL}/run-analysis" \
        --http-method=POST \
        --oidc-service-account-email=${SERVICE_NAME}@${PROJECT_ID}.iam.gserviceaccount.com \
        --time-zone="America/New_York"
fi

echo "✅ Cloud Scheduler configured successfully!"
echo ""
echo "Job details:"
gcloud scheduler jobs describe ${JOB_NAME} \
    --location=${REGION} \
    --project=${PROJECT_ID}

echo ""
echo "To manually trigger the job:"
echo "  gcloud scheduler jobs run ${JOB_NAME} --location=${REGION} --project=${PROJECT_ID}"
