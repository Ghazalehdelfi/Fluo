#!/bin/bash
# =============================================================
# deploy.sh — Push code updates to your Lightsail instance (Docker)
# Run from your Mac whenever you want to deploy changes
# Usage: bash deploy/deploy.sh
# =============================================================

set -euo pipefail

# --- Configuration (edit these) ---
LIGHTSAIL_IP="${LIGHTSAIL_IP:-99.79.22.33}"
SSH_KEY="${SSH_KEY:-./deploy/LightsailDefaultKey-ca-central-1.pem}"
SSH_USER="${SSH_USER:-ubuntu}"
APP_NAME="fluo"
REGION="${AWS_REGION:-ca-central-1}"
ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${APP_NAME}"

# --- Validate ---
if [ "$LIGHTSAIL_IP" = "YOUR_LIGHTSAIL_IP_HERE" ]; then
    echo "ERROR: Set LIGHTSAIL_IP first."
    echo "  export LIGHTSAIL_IP=x.x.x.x"
    exit 1
fi

SSH_CMD="ssh -i $SSH_KEY -o StrictHostKeyChecking=no ${SSH_USER}@${LIGHTSAIL_IP}"

echo "=== Deploying Fluo to $LIGHTSAIL_IP ==="
echo "ECR: ${ECR_URI}"

# --- Build & push to ECR ---
echo "[1/3] Building and pushing image to ECR..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
bash "${SCRIPT_DIR}/ecr-push.sh"

# --- Pull and restart on Lightsail ---
echo "[2/3] Pulling image on server..."
$SSH_CMD "
    aws ecr get-login-password --region ${REGION} | sudo docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com
    sudo docker pull ${ECR_URI}:latest
"

echo "[3/3] Restarting container..."
$SSH_CMD "
    # Copy ubuntu's AWS credentials to root so the Docker daemon (runs as root)
    # can authenticate with CloudWatch Logs via the awslogs driver.
    sudo mkdir -p /root/.aws
    sudo cp /home/${SSH_USER}/.aws/credentials /root/.aws/credentials 2>/dev/null || true
    sudo cp /home/${SSH_USER}/.aws/config /root/.aws/config 2>/dev/null || true
    sudo chmod 600 /root/.aws/credentials 2>/dev/null || true

    sudo docker rm -f ${APP_NAME} 2>/dev/null || true
    sudo docker run -d \
        --name ${APP_NAME} \
        --restart unless-stopped \
        -p 127.0.0.1:8000:8000 \
        -e AWS_REGION=${REGION} \
        -v /home/${SSH_USER}/.aws:/root/.aws:ro \
        --log-driver=awslogs \
        --log-opt awslogs-region=${REGION} \
        --log-opt awslogs-group=/fluo/backend \
        --log-opt awslogs-stream=backend \
        --log-opt awslogs-create-group=true \
        ${ECR_URI}:latest
"

echo ""
echo "=== Deployed successfully! ==="
echo "App: http://$LIGHTSAIL_IP"
echo "Logs: $SSH_CMD 'sudo docker logs -f $APP_NAME'"
