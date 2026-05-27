#!/bin/bash
# =============================================================
# setup-ssl.sh — Add free HTTPS via Let's Encrypt (run on server)
# Usage: bash setup-ssl.sh yourdomain.com
# =============================================================

set -euo pipefail

DOMAIN="learnwithfluo.com" # or pass as first arg: bash setup-ssl.sh yourdomain.com

if [ -z "$DOMAIN" ]; then
    echo "Usage: bash setup-ssl.sh yourdomain.com"
    exit 1
fi

echo "=== Setting up SSL for $DOMAIN ==="

# Install certbot
sudo apt-get install -y -qq certbot python3-certbot-nginx

# Update nginx with real domain
sudo sed -i "s/server_name _;/server_name $DOMAIN;/" /etc/nginx/sites-available/fluo
sudo nginx -t
sudo systemctl reload nginx

# Get certificate
sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email "admin@$DOMAIN" --redirect

# Auto-renewal is set up by certbot automatically
echo ""
echo "=== SSL configured! ==="
echo "App: https://$DOMAIN"
echo "Certificate auto-renews via systemd timer."
