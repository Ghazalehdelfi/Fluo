#!/bin/bash
# =============================================================
# upload-secrets.sh — Store your secrets in AWS SSM Parameter Store
# Run this ONCE from your local machine (requires AWS CLI configured)
# Usage: ./deploy/upload-secrets.sh
# =============================================================

set -euo pipefail

PREFIX="/vocab-practice"
REGION="${AWS_REGION:-ca-central-1}"

echo "=== Uploading secrets to AWS SSM Parameter Store ==="
echo "Region: $REGION"
echo "Prefix: $PREFIX"
echo ""

OPENAI_API_KEY=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
# DATABASE_URL=postgresql://postgres:Fluo-be-setup-GD13@db.woklbozgyfrtroppxhpo.supabase.co:5432/postgres
DATABASE_URL=postgresql://postgres.woklbozgyfrtroppxhpo:Fluo-be-setup-GD13@aws-1-us-east-2.pooler.supabase.com:5432/postgres
STRIPE_SECRET_KEY=sk_test_51TBJg54ibjvp1cMLAFYSMRKdayg6zGSY2hl1U680v9r9d4RA0xibuYoTqyHOPMxj58dBc2llqwni6mTWTwnOsRMh00nzpiKRQD
STRIPE_WEBHOOK_SECRET=whsec_0e52b6965f5e1109de6a7f698761f5a344f0634616649a7f1b5c34324a60de3e
JWT_SECRET=1e8ebd9aab3b95219206d8fb3f3dbc2d3784d0df31082c78a02b85cfb9880885
ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000,http://99.79.22.33,https://learnwithfluo.com,http://learnwithfluo.com

store_param() {
    local name="$1"
    local value="$2"
    if [ -n "$value" ]; then
        aws ssm put-parameter \
            --name "${PREFIX}/${name}" \
            --value "$value" \
            --type SecureString \
            --overwrite \
            --region "$REGION" \
            --no-cli-pager
        echo "  ✓ ${name}"
    else
        echo "  ⏭ ${name} (skipped — empty)"
    fi
}

store_param "OPENAI_API_KEY" "$OPENAI_API_KEY"
store_param "JWT_SECRET" "$JWT_SECRET"
store_param "DATABASE_URL" "$DATABASE_URL"
store_param "STRIPE_SECRET_KEY" "$STRIPE_SECRET_KEY"
store_param "STRIPE_WEBHOOK_SECRET" "$STRIPE_WEBHOOK_SECRET"
# store_param "STRIPE_PUBLISHABLE_KEY" "$STRIPE_PUBLISHABLE_KEY"
# store_param "STRIPE_PRICE_ID" "$STRIPE_PRICE_ID"
store_param "ALLOWED_ORIGINS" "$ALLOWED_ORIGINS"

echo ""
echo "=== Done! Secrets stored in SSM Parameter Store ==="
echo "Your Lightsail instance will fetch these at startup."
