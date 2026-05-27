#!/bin/bash
# =============================================================
# setup-ssl.sh — Add free HTTPS via Let's Encrypt (run on server)
# Usage: bash setup-ssl.sh yourdomain.com
# =============================================================

set -euo pipefail

DOMAIN="${1:-learnwithfluo.com}"
WWW_DOMAIN="www.${DOMAIN}"

if [ -z "$DOMAIN" ]; then
    echo "Usage: bash setup-ssl.sh yourdomain.com"
    exit 1
fi

echo "=== Setting up SSL for $DOMAIN and $WWW_DOMAIN ==="

# Install certbot
sudo apt-get install -y -qq certbot python3-certbot-nginx

# Update nginx with real domains
sudo sed -i -E "s/server_name[[:space:]]+[^;]*;/server_name $DOMAIN $WWW_DOMAIN;/" /etc/nginx/sites-available/fluo
sudo nginx -t
sudo systemctl reload nginx

# Get certificate
sudo certbot --nginx \
    -d "$DOMAIN" \
    -d "$WWW_DOMAIN" \
    --non-interactive \
    --agree-tos \
    --email "admin@$DOMAIN" \
    --redirect \
    --expand

# Auto-renewal is set up by certbot automatically
echo ""
echo "=== SSL configured! ==="
echo "App: https://$DOMAIN"
echo "Certificate auto-renews via systemd timer."
