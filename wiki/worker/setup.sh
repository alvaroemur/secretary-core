#!/bin/bash
# Setup script for wiki-comments-api Worker
# Run: cd wiki/worker && bash setup.sh
set -e

echo "=== Wiki Comments API — Setup ==="
echo ""

# 1. Login to Cloudflare (interactive)
echo "Step 1: Login to Cloudflare..."
npx wrangler login

# 2. Create KV namespace
echo ""
echo "Step 2: Creating KV namespace..."
KV_OUTPUT=$(npx wrangler kv namespace create COMMENTS 2>&1)
echo "$KV_OUTPUT"
KV_ID=$(echo "$KV_OUTPUT" | grep -oP 'id = "\K[^"]+' || echo "")

if [ -z "$KV_ID" ]; then
  echo "Could not extract KV ID automatically."
  echo "Please paste the KV namespace ID from above:"
  read KV_ID
fi

# Update wrangler.toml with the real KV ID
sed -i.bak "s/__PLACEHOLDER__/$KV_ID/" wrangler.toml
rm -f wrangler.toml.bak
echo "Updated wrangler.toml with KV ID: $KV_ID"

# 3. Generate API secret
API_SECRET=$(openssl rand -hex 24)
echo ""
echo "Step 3: Setting API secret..."
echo "$API_SECRET" | npx wrangler secret put API_SECRET

# 4. Deploy
echo ""
echo "Step 4: Deploying Worker..."
npx wrangler deploy

# 5. Get the Worker URL
echo ""
echo "=== DONE ==="
WORKER_URL="https://wiki-comments-api.$(npx wrangler whoami 2>/dev/null | grep -oP '\w+\.workers\.dev' || echo 'YOUR_SUBDOMAIN.workers.dev')"
echo ""
echo "Worker URL: $WORKER_URL"
echo "API Secret: $API_SECRET"
echo ""
echo "Add these to your shell profile (~/.zshrc):"
echo "  export WIKI_COMMENTS_API=\"$WORKER_URL\""
echo "  export WIKI_COMMENTS_SECRET=\"$API_SECRET\""
echo ""
echo "Then rebuild the wiki:"
echo "  cd ../wiki && python3 build/build.py"
