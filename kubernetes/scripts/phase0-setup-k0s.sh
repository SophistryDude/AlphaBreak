#!/bin/bash
# Phase 0: Install k0s and bootstrap the cluster
# ================================================
# Run this ONCE on the EC2 instance to set up k0s.
# After this, run phase1-deploy-flask.sh.
#
# Prerequisites:
#   - EC2 instance (t3.medium minimum, t3.large recommended)
#   - Ubuntu 22.04+
#   - sudo access
#
# Usage:
#   chmod +x kubernetes/scripts/phase0-setup-k0s.sh
#   ./kubernetes/scripts/phase0-setup-k0s.sh

set -e

echo "============================================"
echo " Phase 0: k0s Cluster Setup"
echo "============================================"

# ── Step 1: Install k0s ──────────────────────────────────────────────────────
echo ""
echo "[1/5] Installing k0s..."
if command -v k0s &> /dev/null; then
    echo "  k0s already installed: $(k0s version)"
else
    curl -sSLf https://get.k0s.sh | sudo sh
    echo "  k0s installed: $(sudo k0s version)"
fi

# ── Step 2: Start k0s as single-node controller+worker ──────────────────────
echo ""
echo "[2/5] Starting k0s single-node cluster..."
if sudo k0s status 2>/dev/null | grep -q "running"; then
    echo "  k0s is already running."
else
    sudo k0s install controller --single
    sudo k0s start
    echo "  Waiting for k0s to be ready..."
    sleep 15
    # Wait until the API server responds
    for i in $(seq 1 30); do
        if sudo k0s kubectl get nodes &>/dev/null; then
            echo "  k0s is ready."
            break
        fi
        echo "  Waiting... ($i/30)"
        sleep 5
    done
fi

echo "  Node status:"
sudo k0s kubectl get nodes

# ── Step 3: Create namespace ─────────────────────────────────────────────────
echo ""
echo "[3/5] Creating trading-system namespace..."
REPO_DIR="/home/ubuntu/Securities_prediction_model"
sudo k0s kubectl apply -f $REPO_DIR/kubernetes/namespace.yaml
echo "  Namespace created."

# ── Step 4: Create secrets ───────────────────────────────────────────────────
echo ""
echo "[4/5] Creating secrets..."
echo ""
echo "  IMPORTANT: You must edit the secrets before deploying!"
echo "  Either:"
echo "    a) Edit kubernetes/secrets.yaml with real values, then run:"
echo "       sudo k0s kubectl apply -f $REPO_DIR/kubernetes/secrets.yaml"
echo "    b) Create secrets manually:"
echo "       sudo k0s kubectl create secret generic trading-secrets -n trading-system \\"
echo "         --from-literal=secret-key=\"\$(openssl rand -hex 32)\" \\"
echo "         --from-literal=api-key=\"\$(openssl rand -hex 32)\" \\"
echo "         --from-literal=airflow-fernet-key=\"\$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')\" \\"
echo "         --from-literal=airflow-admin-password=\"your-airflow-password\" \\"
echo "         --from-literal=postgres-password=\"your-airflow-db-password\" \\"
echo "         --from-literal=timeseries-postgres-password=\"your-timeseries-db-password\" \\"
echo "         --from-literal=timeseries-postgres-user=\"trading\" \\"
echo "         --from-literal=timeseries-postgres-db=\"trading_data\" \\"
echo "         --from-literal=airflow-db-conn=\"postgresql+psycopg2://airflow:your-airflow-db-password@airflow-postgres.trading-system:5432/airflow\" \\"
echo "         --from-literal=alpha-vantage-key=\"your-alpha-vantage-key\""
echo ""
read -p "  Have you created the secrets? (y/n): " SECRETS_READY
if [ "$SECRETS_READY" != "y" ]; then
    echo "  Please create secrets before proceeding to Phase 1."
    echo "  Exiting."
    exit 0
fi

# ── Step 5: Apply ConfigMap and StorageClass ──────────────────────────────────
echo ""
echo "[5/5] Applying ConfigMap and storage resources..."
sudo k0s kubectl apply -f $REPO_DIR/kubernetes/configmap.yaml
sudo k0s kubectl apply -f $REPO_DIR/kubernetes/persistent-volume.yaml
echo "  ConfigMap and PersistentVolumes created."

echo ""
echo "============================================"
echo " Phase 0 Complete!"
echo "============================================"
echo ""
echo " k0s cluster is running in single-node mode."
echo " Namespace: trading-system"
echo " ConfigMap: trading-api-config"
echo ""
echo " Cluster info:"
sudo k0s kubectl cluster-info
echo ""
echo " Next: Run phase1-deploy-flask.sh"
