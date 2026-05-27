#!/bin/bash
# =============================================================
# setup-server.sh — First-time Lightsail server setup (Docker)
# Run from your LOCAL Mac: bash deploy/setup-server.sh
# =============================================================

set -euo pipefail

# --- Configuration (edit these) ---
LIGHTSAIL_IP="${LIGHTSAIL_IP:-99.79.22.33}"
SSH_KEY="${SSH_KEY:-./LightsailDefaultKey-ca-central-1.pem}"
SSH_USER="${SSH_USER:-ubuntu}"

APP_NAME="fluo"
REGION="${AWS_REGION:-ca-central-1}"
ACCOUNT_ID="779400169222"
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${APP_NAME}"

# --- Validate ---
if [ "$LIGHTSAIL_IP" = "YOUR_LIGHTSAIL_IP_HERE" ]; then
    echo "ERROR: Set LIGHTSAIL_IP first."
    echo "  export LIGHTSAIL_IP=x.x.x.x"
    exit 1
fi

SSH_CMD="ssh -i $SSH_KEY -o StrictHostKeyChecking=no ${SSH_USER}@${LIGHTSAIL_IP}"

echo "=== Fluo — Lightsail Server Setup (Docker) ==="

# --- Install Docker ---
echo "[1/4] Installing Docker..."
$SSH_CMD 'if ! command -v docker &> /dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq ca-certificates curl gnupg
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update -qq
    sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
    sudo usermod -aG docker $USER
    echo "Docker installed."
else
    echo "Docker already installed."
fi'

# --- Install AWS CLI (for SSM access) ---
echo "[2/4] Installing AWS CLI (if needed)..."
$SSH_CMD 'if ! command -v aws &> /dev/null; then
    curl -s "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "/tmp/awscliv2.zip"
    sudo apt-get install -y -qq unzip
    unzip -q /tmp/awscliv2.zip -d /tmp
    sudo /tmp/aws/install
    rm -rf /tmp/aws /tmp/awscliv2.zip
    echo "AWS CLI installed."
else
    echo "AWS CLI already installed."
fi'

# --- Configure Nginx as reverse proxy ---
echo "[3/4] Setting up Nginx..."
$SSH_CMD 'sudo apt-get install -y -qq nginx'
$SSH_CMD 'sudo tee /etc/nginx/sites-available/'"$APP_NAME"' > /dev/null <<\NGINXEOF
server {
    listen 80;
    server_name _;

    client_max_body_size 25M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
NGINXEOF
sudo ln -sf /etc/nginx/sites-available/'"$APP_NAME"' /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx'

# --- Pull image from ECR and run container ---
echo "[4/4] Pulling and starting container from ECR..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Build & push from local Mac first
bash "${SCRIPT_DIR}/ecr-push.sh"

# Pull & run on server
$SSH_CMD "
    aws ecr get-login-password --region ${REGION} | sudo docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com
    sudo docker pull ${ECR_URI}:latest
    sudo docker rm -f ${APP_NAME} 2>/dev/null || true
    sudo docker run -d \
        --name ${APP_NAME} \
        --restart unless-stopped \
        -p 127.0.0.1:8000:8000 \
        -e AWS_REGION=${REGION} \
        -v /home/${SSH_USER}/.aws:/root/.aws:ro \
        ${ECR_URI}:latest
"

echo ""
echo "=== Setup complete! ==="
echo "App running at http://$LIGHTSAIL_IP"
echo ""
echo "Useful commands:"
echo "  $SSH_CMD 'sudo docker logs -f $APP_NAME'       # View logs"
echo "  $SSH_CMD 'sudo docker restart $APP_NAME'        # Restart"
echo "  $SSH_CMD 'sudo docker ps'                       # Check status"
