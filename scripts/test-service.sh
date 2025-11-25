#!/bin/bash

# Test the deployed service
# Usage: ./scripts/test-service.sh [service-url]

set -e

SERVICE_URL=${1:-"http://localhost:8080"}

echo "🧪 Testing service at: ${SERVICE_URL}"
echo ""

# Test health endpoint
echo "1. Testing /health endpoint..."
curl -s "${SERVICE_URL}/health" | jq '.'
echo ""

# Test ready endpoint
echo "2. Testing /ready endpoint..."
curl -s "${SERVICE_URL}/ready" | jq '.'
echo ""

# Test status endpoint
echo "3. Testing /status endpoint..."
curl -s "${SERVICE_URL}/status" | jq '.'
echo ""

# Test root endpoint
echo "4. Testing root endpoint..."
curl -s "${SERVICE_URL}/" | jq '.'
echo ""

# Test run-analysis endpoint (async)
echo "5. Testing /run-analysis endpoint (async)..."
curl -s -X POST "${SERVICE_URL}/run-analysis?async_execution=true" | jq '.'
echo ""

echo "✅ All tests completed!"
