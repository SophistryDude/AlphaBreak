#!/bin/bash
# Phase 2: Deploy Airflow into k0s
# ===================================
# Run this script AFTER phase1-deploy-flask.sh has completed successfully.
# Deploys Airflow with KubernetesExecutor: metadata DB, scheduler, webserver.
#
# Prerequisites:
#   - k0s running with trading-system namespace
#   - trading-secrets already created (with airflow-db-conn, airflow-fernet-key, etc.)
#   - Phase 1 complete (Flask API running in k0s)
#
# Usage:
#   chmod +x kubernetes/scripts/phase2-deploy-airflow.sh
#   ./kubernetes/scripts/phase2-deploy-airflow.sh

set -e  # Exit on any error

REPO_DIR="/home/ubuntu/Securities_prediction_model"
K0S="sudo k0s kubectl"
NS="trading-system"

echo "============================================"
echo " Phase 2: Airflow → k0s"
echo "============================================"

# ── Step 1: Build Airflow Docker image ────────────────────────────────────────
echo ""
echo "[1/7] Building airflow-trading Docker image..."
cd /home/ubuntu
sudo docker build -f Securities_prediction_model/Dockerfile.airflow \
    -t airflow-trading:latest \
    Securities_prediction_model/
echo "  Build complete."

# ── Step 2: Import image into k0s containerd ─────────────────────────────────
echo ""
echo "[2/7] Importing airflow-trading image into k0s containerd..."
sudo docker save airflow-trading:latest | sudo k0s ctr images import -
echo "  Verifying image in containerd:"
sudo k0s ctr images list | grep airflow-trading

# ── Step 3: Deploy Airflow metadata database ──────────────────────────────────
echo ""
echo "[3/7] Deploying Airflow metadata database (postgres:15-alpine)..."
$K0S apply -f $REPO_DIR/kubernetes/airflow/airflow-postgres.yaml
echo "  Waiting for Airflow DB to be ready (up to 2 minutes)..."
$K0S wait deployment/airflow-postgres -n $NS \
    --for=condition=available --timeout=120s
echo "  Airflow DB status:"
$K0S get pods -n $NS -l app=airflow-postgres

# ── Step 4: Deploy RBAC (ServiceAccount + Role for scheduler) ─────────────────
echo ""
echo "[4/7] Creating Airflow RBAC resources..."
$K0S apply -f $REPO_DIR/kubernetes/airflow/airflow-rbac.yaml
echo "  ServiceAccount and Role created."

# ── Step 5: Deploy pod template ConfigMap ─────────────────────────────────────
echo ""
echo "[5/7] Deploying KubernetesExecutor pod template..."
$K0S apply -f $REPO_DIR/kubernetes/airflow/airflow-pod-template.yaml
echo "  Pod template ConfigMap created."

# ── Step 6: Deploy Airflow scheduler ──────────────────────────────────────────
echo ""
echo "[6/7] Deploying Airflow scheduler (KubernetesExecutor)..."
$K0S apply -f $REPO_DIR/kubernetes/airflow/airflow-scheduler.yaml
echo "  Waiting for scheduler to be ready (up to 3 minutes)..."
$K0S wait deployment/airflow-scheduler -n $NS \
    --for=condition=available --timeout=180s
echo "  Scheduler status:"
$K0S get pods -n $NS -l component=scheduler

# ── Step 7: Deploy Airflow webserver + service ────────────────────────────────
echo ""
echo "[7/7] Deploying Airflow webserver..."
$K0S apply -f $REPO_DIR/kubernetes/airflow/airflow-deployment.yaml
$K0S apply -f $REPO_DIR/kubernetes/airflow/airflow-webserver-service.yaml
echo "  Waiting for webserver to be ready (up to 3 minutes)..."
$K0S wait deployment/airflow-webserver -n $NS \
    --for=condition=available --timeout=180s
echo "  Webserver status:"
$K0S get pods -n $NS -l component=webserver

# ── Verify ────────────────────────────────────────────────────────────────────
echo ""
echo "Verifying Airflow health on NodePort 30880..."
sleep 10
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:30880/health)
if [ "$HTTP_STATUS" = "200" ]; then
    echo "  Airflow webserver responding (HTTP $HTTP_STATUS)"
else
    echo "  Airflow webserver returned HTTP $HTTP_STATUS (may still be starting)"
    echo "  Check logs: $K0S logs -n $NS -l component=webserver --tail=50"
fi

# ── Stop bare-metal Airflow ───────────────────────────────────────────────────
echo ""
echo "Stopping bare-metal Airflow..."
sudo systemctl stop airflow-scheduler 2>/dev/null || sudo pkill -f "airflow scheduler" || true
sudo systemctl stop airflow-webserver 2>/dev/null || sudo pkill -f "airflow webserver" || true
sudo systemctl disable airflow-scheduler 2>/dev/null || true
sudo systemctl disable airflow-webserver 2>/dev/null || true
echo "  Bare-metal Airflow stopped."

echo ""
echo "============================================"
echo " Phase 2 Complete!"
echo "============================================"
echo ""
echo " Airflow is now running in k0s with KubernetesExecutor."
echo " Webserver: http://127.0.0.1:30880"
echo " Login: admin / (password from trading-secrets)"
echo ""
echo " All pods:"
$K0S get pods -n $NS
echo ""
echo " DAGs are baked into the airflow-trading image."
echo " portfolio_update DAG runs weekdays at 9 AM EST (14:00 UTC)."
echo ""
echo " Next: Run phase3-migrate-postgres.sh (when ready to containerize TimescaleDB)"
echo ""
echo " Rollback (if needed):"
echo "   $K0S delete -f $REPO_DIR/kubernetes/airflow/"
echo "   sudo systemctl start airflow-scheduler airflow-webserver"
