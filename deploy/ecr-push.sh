#!/bin/bash
# =============================================================
# ecr-push.sh — Create ECR repo (if needed), build & push image
# Run from your Mac: bash deploy/ecr-push.sh
# =============================================================

set -euo pipefail

APP_NAME="fluo"
REGION="${AWS_REGION:-ca-central-1}"
ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${APP_NAME}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== ECR Push: ${APP_NAME} ==="
echo "Region: ${REGION}"
echo "ECR:    ${ECR_URI}"
echo ""

# --- Ensure ECR repo exists ---
echo "[1/3] Checking ECR repository exists..."
if ! aws ecr describe-repositories --repository-names "${APP_NAME}" --region "${REGION}" >/dev/null 2>&1; then
    echo "ERROR: ECR repository '${APP_NAME}' was not found in ${REGION} for account ${ACCOUNT_ID}."
    echo "Create it once with an admin identity:"
    echo "  aws ecr create-repository --repository-name ${APP_NAME} --region ${REGION} --image-scanning-configuration scanOnPush=true"
    exit 1
fi

# --- Log in to ECR ---
echo "[2/3] Logging in to ECR..."
aws ecr get-login-password --region "${REGION}" | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

# --- Build for linux/amd64 (Lightsail is x86) and push ---
echo "[3/3] Building and pushing image (linux/amd64)..."
docker buildx build --platform linux/amd64 -t "${ECR_URI}:latest" --push "${PROJECT_DIR}"

echo ""
echo "=== Done! Image pushed to ${ECR_URI}:latest ==="
