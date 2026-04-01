#!/bin/bash
# Phase 1: Deploy Flask API into k0s
# ====================================
# Run this script AFTER phase0-setup-k0s.sh has completed.
# Deploys: postgres bridge endpoint, Redis, Flask API.
#
# Prerequisites:
#   - k0s running (phase0 complete)
#   - trading-secrets created
#   - PostgreSQL running on bare metal (will bridge via Endpoints)
#
# Usage:
#   chmod +x kubernetes/scripts/phase1-deploy-flask.sh
#   ./kubernetes/scripts/phase1-deploy-flask.sh

set -e  # Exit on any error

REPO_DIR="/home/ubuntu/Securities_prediction_model"
K0S="sudo k0s kubectl"
NS="trading-system"

echo "============================================"
echo " Phase 1: Flask API → k0s"
echo "============================================"

# ── Step 1: Route postgres-timeseries-service to host Postgres ──────────────
echo ""
echo "[1/8] Routing postgres-timeseries-service to host Postgres..."
$K0S apply -f $REPO_DIR/kubernetes/postgres-host-endpoints.yaml
echo "  Verifying endpoint..."
$K0S get endpoints postgres-timeseries-service -n $NS

# ── Step 2: Deploy Redis ──────────────────────────────────────────────────────
echo ""
echo "[2/8] Deploying Redis..."
$K0S apply -f $REPO_DIR/kubernetes/redis-deployment.yaml
echo "  Waiting for Redis to be ready (up to 1 minute)..."
$K0S wait deployment/redis -n $NS \
    --for=condition=available --timeout=60s
echo "  Redis status:"
$K0S get pods -n $NS -l app=redis

# ── Step 3: Install Docker (if not present) ──────────────────────────────────
echo ""
echo "[3/8] Checking Docker..."
if ! command -v docker &> /dev/null; then
    echo "  Installing Docker..."
    sudo apt-get update -q
    sudo apt-get install -y docker.io
    sudo usermod -aG docker ubuntu
    echo "  Docker installed."
fi
docker --version || sudo docker --version

# ── Step 4: Build Docker image ───────────────────────────────────────────────
echo ""
echo "[4/8] Building trading-api Docker image..."
cd $REPO_DIR
sudo docker build -f flask_app/Dockerfile -t trading-api:latest .
echo "  Build complete."

# ── Step 5: Import image into k0s containerd ─────────────────────────────────
echo ""
echo "[5/8] Importing image into k0s containerd..."
sudo docker save trading-api:latest | sudo k0s ctr images import -
echo "  Verifying image in containerd:"
sudo k0s ctr images list | grep trading-api

# ── Step 6: Deploy Flask API service ──────────────────────────────────────────
echo ""
echo "[6/8] Creating API service (NodePort 30427)..."
$K0S apply -f $REPO_DIR/kubernetes/api-service.yaml

# ── Step 7: Deploy Flask API pod ──────────────────────────────────────────────
echo ""
echo "[7/8] Deploying Flask API pod..."
$K0S apply -f $REPO_DIR/kubernetes/api-deployment.yaml
$K0S apply -f $REPO_DIR/kubernetes/api-hpa.yaml

echo "  Waiting for pod to be ready (up to 3 minutes)..."
$K0S wait deployment/trading-api -n $NS \
    --for=condition=available --timeout=180s

echo "  Pod status:"
$K0S get pods -n $NS -l app=trading-api

# ── Step 8: Test the pod then update Nginx ───────────────────────────────────
echo ""
echo "[8/8] Testing API pod via NodePort 30427..."
sleep 5
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:30427/api/health)
if [ "$HTTP_STATUS" = "200" ]; then
    echo "  API pod responding (HTTP $HTTP_STATUS)"
    echo ""
    echo "  Updating Nginx to proxy to k0s NodePort..."
    sudo sed -i 's|proxy_pass http://127.0.0.1:5000/api/;|proxy_pass http://127.0.0.1:30427/api/;|g' \
        /etc/nginx/sites-enabled/alphabreak.vip
    sudo nginx -t && sudo nginx -s reload
    echo "  Nginx updated and reloaded"
    echo ""
    echo "  Stopping bare-metal gunicorn..."
    sudo pkill -f "gunicorn.*wsgi" || true
    sudo systemctl disable trading-api 2>/dev/null || true
    echo "  Bare-metal gunicorn stopped"
else
    echo "  API pod not responding (HTTP $HTTP_STATUS)"
    echo "  Check logs: $K0S logs -n $NS -l app=trading-api --tail=50"
    echo "  Nginx NOT updated. Bare-metal gunicorn still running."
    exit 1
fi

echo ""
echo "============================================"
echo " Phase 1 Complete!"
echo "============================================"
echo ""
echo " Flask API is now running in k0s."
echo " Site: https://alphabreak.vip"
echo " API via NodePort: http://127.0.0.1:30427"
echo ""
echo " All pods:"
$K0S get pods -n $NS
echo ""
echo " Next: Run phase2-deploy-airflow.sh"
echo ""
echo " Rollback (if needed):"
echo "   sudo sed -i 's|30427|5000|g' /etc/nginx/sites-enabled/alphabreak.vip"
echo "   sudo nginx -s reload"
echo "   sudo systemctl start trading-api"
