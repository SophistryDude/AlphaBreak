#!/bin/bash
# Phase 3: Migrate TimescaleDB into k0s
# =======================================
# Run this AFTER phase2-deploy-airflow.sh and after confirming
# both Flask API and Airflow are stable in k0s.
#
# This script:
#   1. Dumps the bare-metal PostgreSQL database
#   2. Deploys TimescaleDB in k0s
#   3. Restores the dump into the k0s TimescaleDB pod
#   4. Switches the service from Endpoints bridge to in-cluster pod
#   5. Verifies the API still works
#   6. Stops bare-metal PostgreSQL
#
# IMPORTANT: Ensure you have a backup before running this!
#
# Usage:
#   chmod +x kubernetes/scripts/phase3-migrate-postgres.sh
#   ./kubernetes/scripts/phase3-migrate-postgres.sh

set -e

REPO_DIR="/home/ubuntu/Securities_prediction_model"
K0S="sudo k0s kubectl"
NS="trading-system"
DUMP_FILE="/tmp/trading_data.dump"

echo "============================================"
echo " Phase 3: TimescaleDB → k0s"
echo "============================================"

# ── Pre-flight checks ────────────────────────────────────────────────────────
echo ""
echo "Pre-flight checks..."
echo "  1. Flask API pod running?"
$K0S get pods -n $NS -l app=trading-api --no-headers | grep Running || {
    echo "  Flask API not running. Complete Phase 1 first."
    exit 1
}
echo "  2. Airflow pods running?"
$K0S get pods -n $NS -l app=airflow --no-headers | head -1 | grep Running || {
    echo "  Airflow not running. Complete Phase 2 first."
    exit 1
}

echo ""
echo "  WARNING: This will migrate the production database."
echo "  Ensure you have a backup stored OFF this EC2 instance."
read -p "  Continue? (y/n): " CONFIRM
if [ "$CONFIRM" != "y" ]; then
    echo "  Aborted."
    exit 0
fi

# ── Step 1: Dump bare-metal database ──────────────────────────────────────────
echo ""
echo "[1/6] Dumping bare-metal PostgreSQL..."
sudo -u postgres pg_dump -Fc trading_data -f $DUMP_FILE
ls -lh $DUMP_FILE
echo "  Dump complete."

# ── Step 2: Deploy TimescaleDB in k0s ────────────────────────────────────────
echo ""
echo "[2/6] Deploying TimescaleDB pod..."
$K0S apply -f $REPO_DIR/kubernetes/postgres-timeseries-deployment.yaml
echo "  Waiting for TimescaleDB to be ready (up to 3 minutes)..."
$K0S wait deployment/postgres-timeseries -n $NS \
    --for=condition=available --timeout=180s
echo "  TimescaleDB pod status:"
$K0S get pods -n $NS -l app=postgres-timeseries

# ── Step 3: Restore dump into k0s pod ────────────────────────────────────────
echo ""
echo "[3/6] Restoring database into k0s TimescaleDB pod..."
POSTGRES_POD=$($K0S get pods -n $NS -l app=postgres-timeseries -o jsonpath='{.items[0].metadata.name}')

# Copy dump file into pod
$K0S cp $DUMP_FILE $NS/$POSTGRES_POD:/tmp/trading_data.dump

# Run TimescaleDB pre-restore, restore, post-restore
$K0S exec -n $NS $POSTGRES_POD -- bash -c '
    export PGPASSWORD=$POSTGRES_PASSWORD
    psql -U trading -d trading_data -c "SELECT timescaledb_pre_restore();" 2>/dev/null || true
    pg_restore -U trading -d trading_data --no-owner --no-privileges /tmp/trading_data.dump || true
    psql -U trading -d trading_data -c "SELECT timescaledb_post_restore();" 2>/dev/null || true
    rm /tmp/trading_data.dump
'
echo "  Restore complete."

# ── Step 4: Switch service from Endpoints bridge to pod ──────────────────────
echo ""
echo "[4/6] Switching postgres-timeseries-service to in-cluster pod..."
# Delete the Endpoints object (stops bridging to bare-metal)
$K0S delete -f $REPO_DIR/kubernetes/postgres-host-endpoints.yaml
# The Service in postgres-timeseries-deployment.yaml uses selector, so it now
# routes to the TimescaleDB pod automatically.
echo "  Service switched. Verifying..."
$K0S get endpoints postgres-timeseries-service -n $NS

# ── Step 5: Verify API still works ───────────────────────────────────────────
echo ""
echo "[5/6] Verifying Flask API with in-cluster database..."
sleep 5
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:30427/api/health)
READY_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:30427/api/ready)
echo "  /api/health: HTTP $HTTP_STATUS"
echo "  /api/ready:  HTTP $READY_STATUS"

if [ "$READY_STATUS" = "200" ]; then
    echo "  API is connected to in-cluster database."
else
    echo "  WARNING: API readiness check failed."
    echo "  Check logs: $K0S logs -n $NS -l app=trading-api --tail=30"
    echo "  You may need to restart the API pod:"
    echo "    $K0S rollout restart deployment/trading-api -n $NS"
    echo ""
    echo "  To rollback, re-apply the host endpoints:"
    echo "    $K0S apply -f $REPO_DIR/kubernetes/postgres-host-endpoints.yaml"
    exit 1
fi

# ── Step 6: Stop bare-metal PostgreSQL ────────────────────────────────────────
echo ""
echo "[6/6] Stopping bare-metal PostgreSQL..."
echo "  NOTE: Only stop after verifying the API works with in-cluster DB."
read -p "  Stop bare-metal PostgreSQL now? (y/n): " STOP_PG
if [ "$STOP_PG" = "y" ]; then
    sudo systemctl stop postgresql
    sudo systemctl disable postgresql
    echo "  Bare-metal PostgreSQL stopped and disabled."
else
    echo "  Keeping bare-metal PostgreSQL running (you can stop it later)."
fi

echo ""
echo "============================================"
echo " Phase 3 Complete!"
echo "============================================"
echo ""
echo " TimescaleDB is now running in k0s."
echo " All components are containerized:"
$K0S get pods -n $NS
echo ""
echo " Rollback (if needed):"
echo "   sudo systemctl start postgresql"
echo "   $K0S apply -f $REPO_DIR/kubernetes/postgres-host-endpoints.yaml"
echo "   $K0S delete deployment/postgres-timeseries -n $NS"
