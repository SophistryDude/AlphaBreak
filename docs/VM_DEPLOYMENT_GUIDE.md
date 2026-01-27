# VM Deployment Guide - Trading System Local Testing Environment

Complete guide to set up a VM with Kubernetes, Airflow, PostgreSQL, and web interface for testing the trading prediction system.

---

## 🎯 Overview

**What We're Building**:
- Virtual Machine (Ubuntu 22.04 LTS)
- Kubernetes cluster (minikube)
- Airflow (orchestration)
- PostgreSQL with TimescaleDB (time series data)
- Flask API (predictions)
- Frontend web interface
- All accessible from your host machine

**System Requirements**:
- **Host OS**: Windows 11, macOS, or Linux
- **RAM**: 16GB minimum (8GB for VM, rest for host)
- **Storage**: 100GB free space
- **CPU**: 4+ cores
- **Virtualization**: Enabled in BIOS

---

## 📦 Part 1: Set Up Virtual Machine

### Option A: VirtualBox (Free, Recommended for Testing)

**Step 1: Install VirtualBox**
```bash
# Windows: Download from https://www.virtualbox.org/wiki/Downloads
# macOS: brew install --cask virtualbox
# Linux: sudo apt install virtualbox
```

**Step 2: Download Ubuntu Server**
```bash
# Download Ubuntu 22.04 LTS Server ISO
# https://ubuntu.com/download/server
```

**Step 3: Create VM**

1. Open VirtualBox → New
2. Configure:
   - **Name**: TradingSystem
   - **Type**: Linux
   - **Version**: Ubuntu (64-bit)
   - **Memory**: 8192 MB (8GB)
   - **Hard Disk**: Create virtual hard disk (80GB, dynamically allocated)
   - **CPU**: 4 cores
   - **Network**: Bridged Adapter (for host access)

3. Settings → Storage:
   - Controller: IDE → Empty → Choose Ubuntu ISO

4. Start VM and install Ubuntu:
   - Language: English
   - Keyboard: Your layout
   - Network: Use DHCP
   - Storage: Use entire disk
   - Profile:
     - Name: tradingadmin
     - Server name: trading-vm
     - Username: tradingadmin
     - Password: [your-secure-password]
   - SSH: Install OpenSSH server (CHECK THIS!)
   - Packages: Skip for now

5. Reboot after installation

**Step 4: Configure Network for Host Access**

```bash
# On VM, get IP address
ip addr show

# Note the IP (e.g., 192.168.1.100)
# You'll use this to access from host machine

# Test SSH from host:
ssh tradingadmin@192.168.1.100
```

**Step 5: Update System**

```bash
# SSH into VM
ssh tradingadmin@192.168.1.100

# Update packages
sudo apt update && sudo apt upgrade -y

# Install essential tools
sudo apt install -y curl wget git vim htop net-tools
```

---

### Option B: AWS EC2 (Cloud, Costs Money)

**Step 1: Launch EC2 Instance**

```bash
# AWS Console → EC2 → Launch Instance

Configuration:
- AMI: Ubuntu Server 22.04 LTS
- Instance Type: t3.xlarge (4 vCPU, 16 GB RAM)
- Storage: 80 GB gp3
- Security Group:
  - SSH (22) - Your IP
  - HTTP (80) - Your IP
  - HTTPS (443) - Your IP
  - Custom TCP (5000) - Your IP  # Flask API
  - Custom TCP (8080) - Your IP  # Airflow
  - Custom TCP (30000-32767) - Your IP  # Kubernetes NodePort

# Download .pem key
chmod 400 trading-key.pem
ssh -i trading-key.pem ubuntu@<ec2-public-ip>
```

---

## 📦 Part 2: Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group (no sudo needed)
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker --version
docker run hello-world
```

---

## 📦 Part 3: Install Kubernetes (minikube)

**Step 1: Install kubectl**

```bash
# Download kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"

# Install
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Verify
kubectl version --client
```

**Step 2: Install minikube**

```bash
# Download minikube
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64

# Install
sudo install minikube-linux-amd64 /usr/local/bin/minikube

# Verify
minikube version
```

**Step 3: Start minikube**

```bash
# Start with Docker driver
minikube start --driver=docker --memory=6144 --cpus=4

# Verify
kubectl get nodes
# Should show: minikube   Ready    control-plane   1m    v1.28.x

# Enable ingress addon (for external access)
minikube addons enable ingress

# Enable metrics-server (for autoscaling)
minikube addons enable metrics-server
```

**Step 4: Configure kubectl**

```bash
# Set default namespace
kubectl config set-context --current --namespace=trading-system

# Verify
kubectl cluster-info
```

---

## 📦 Part 4: Set Up PostgreSQL with TimescaleDB

**Step 1: Create Namespace**

```bash
# Clone your trading system repo
git clone https://github.com/yourusername/trading-system.git
cd trading-system

# Create namespace
kubectl apply -f kubernetes/namespace.yaml
```

**Step 2: Update Secrets**

```bash
# Generate secure passwords
export POSTGRES_PASSWORD=$(openssl rand -base64 32)
export TIMESERIES_PASSWORD=$(openssl rand -base64 32)
export API_KEY=$(openssl rand -base64 32)
export FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Update secrets file
cat > kubernetes/secrets-local.yaml << EOF
apiVersion: v1
kind: Secret
metadata:
  name: trading-secrets
  namespace: trading-system
type: Opaque
stringData:
  api-key: "$API_KEY"
  secret-key: "$API_KEY"
  alpha-vantage-key: "YOUR_ALPHA_VANTAGE_KEY"  # Get from https://www.alphavantage.co/
  airflow-admin-user: "admin"
  airflow-admin-password: "admin123"
  airflow-fernet-key: "$FERNET_KEY"
  postgres-password: "$POSTGRES_PASSWORD"
  timeseries-postgres-password: "$TIMESERIES_PASSWORD"
  timeseries-postgres-user: "trading"
  timeseries-postgres-db: "trading_data"
EOF

# Apply secrets
kubectl apply -f kubernetes/secrets-local.yaml
```

**Step 3: Deploy PostgreSQL**

```bash
# Deploy TimescaleDB
kubectl apply -f kubernetes/postgres-timeseries-deployment.yaml

# Wait for pod to be ready
kubectl wait --for=condition=ready pod -l app=postgres-timeseries -n trading-system --timeout=300s

# Verify
kubectl get pods -n trading-system
# Should show: postgres-timeseries-xxx   1/1     Running

# Test connection
kubectl exec -it deployment/postgres-timeseries -n trading-system -- psql -U trading -d trading_data -c "SELECT version();"
```

**Step 4: Initialize Database Schema**

```bash
# Copy SQL init script to pod
kubectl cp kubernetes/postgres-timeseries-deployment.yaml postgres-timeseries-xxx:/tmp/ -n trading-system

# Or connect and run manually
kubectl exec -it deployment/postgres-timeseries -n trading-system -- psql -U trading -d trading_data

# Inside psql:
CREATE EXTENSION IF NOT EXISTS timescaledb;

# Run all CREATE TABLE statements from kubernetes/postgres-timeseries-deployment.yaml
# (Lines with CREATE TABLE stock_prices, technical_indicators, etc.)

# Verify tables
\dt
# Should show: stock_prices, technical_indicators, engineered_features, etc.

# Exit
\q
```

---

## 📦 Part 5: Deploy Redis

```bash
# Deploy Redis
kubectl apply -f kubernetes/redis-deployment.yaml

# Wait for ready
kubectl wait --for=condition=ready pod -l app=redis -n trading-system --timeout=120s

# Test
kubectl exec -it deployment/redis -n trading-system -- redis-cli ping
# Should return: PONG
```

---

## 📦 Part 6: Build and Deploy Flask API

**Step 1: Build Docker Image**

```bash
cd flask_app

# Build image
docker build -t trading-api:latest .

# Load into minikube (so minikube can use it)
minikube image load trading-api:latest

# Verify
minikube image ls | grep trading-api
```

**Step 2: Create Models Directory**

```bash
# Create persistent volume for models
kubectl apply -f kubernetes/persistent-volume.yaml

# Create directory in minikube for models
minikube ssh
sudo mkdir -p /mnt/data/trading-models
sudo mkdir -p /mnt/data/trading-logs
exit
```

**Step 3: Deploy API**

```bash
# Update api-deployment.yaml to use local image
# Change: image: your-registry.com/trading-api:latest
# To: image: trading-api:latest
# And add: imagePullPolicy: Never

cd kubernetes
kubectl apply -f api-deployment.yaml
kubectl apply -f api-service.yaml

# Wait for ready
kubectl wait --for=condition=ready pod -l app=trading-api -n trading-system --timeout=300s

# Check logs
kubectl logs -f deployment/trading-api -n trading-system
```

**Step 4: Expose API to Host**

```bash
# Port forward to access from host machine
kubectl port-forward svc/trading-api-service 5000:5000 -n trading-system --address=0.0.0.0 &

# Test from host machine browser:
# http://192.168.1.100:5000/api/health
# Should return: {"status": "healthy", ...}
```

---

## 📦 Part 7: Deploy Airflow

**Step 1: Deploy Airflow PostgreSQL**

```bash
kubectl apply -f kubernetes/airflow/airflow-postgres.yaml

# Wait for ready
kubectl wait --for=condition=ready pod -l app=postgres -n trading-system --timeout=300s
```

**Step 2: Create DAGs ConfigMap**

```bash
# Create ConfigMap from DAGs directory
kubectl create configmap airflow-dags \
  --from-file=kubernetes/airflow/dags/ \
  -n trading-system \
  --dry-run=client -o yaml | kubectl apply -f -
```

**Step 3: Initialize Airflow Database**

```bash
# Deploy Airflow scheduler (will init DB)
kubectl apply -f kubernetes/airflow/airflow-scheduler.yaml

# Wait for init to complete (check logs)
kubectl logs -f deployment/airflow-scheduler -n trading-system

# Look for: "Database migration completed successfully"
```

**Step 4: Deploy Airflow Components**

```bash
# Deploy webserver
kubectl apply -f kubernetes/airflow/airflow-deployment.yaml

# Deploy workers
kubectl apply -f kubernetes/airflow/airflow-worker.yaml

# Deploy service
kubectl apply -f kubernetes/airflow/airflow-webserver-service.yaml

# Wait for all pods
kubectl wait --for=condition=ready pod -l app=airflow-webserver -n trading-system --timeout=300s
kubectl wait --for=condition=ready pod -l app=airflow-worker -n trading-system --timeout=300s
```

**Step 5: Access Airflow UI**

```bash
# Port forward
kubectl port-forward svc/airflow-webserver 8080:8080 -n trading-system --address=0.0.0.0 &

# Access from host browser:
# http://192.168.1.100:8080
# Username: admin
# Password: admin123 (from secrets)
```

---

## 📦 Part 8: Deploy Frontend Web Interface

**Step 1: Serve Frontend Locally (Simple)**

```bash
# On your host machine (not VM)
cd frontend
python -m http.server 8000

# Access: http://localhost:8000
```

**Step 2: OR Deploy to VM (Better)**

```bash
# On VM, install nginx
sudo apt install -y nginx

# Copy frontend files to nginx
sudo cp -r frontend/* /var/www/html/

# Update API URL in frontend/app.js
sudo vim /var/www/html/app.js

# Change:
# API_BASE_URL: 'http://localhost:5000'
# To:
# API_BASE_URL: 'http://192.168.1.100:5000'  # Your VM IP

# Restart nginx
sudo systemctl restart nginx

# Access from host browser:
# http://192.168.1.100
```

**Step 3: OR Deploy to Kubernetes (Production-like)**

```bash
# Create nginx ConfigMap
kubectl create configmap frontend-files \
  --from-file=frontend/ \
  -n trading-system

# Create deployment
cat > kubernetes/frontend-deployment.yaml << 'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: trading-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
      - name: nginx
        image: nginx:alpine
        ports:
        - containerPort: 80
        volumeMounts:
        - name: frontend-files
          mountPath: /usr/share/nginx/html
      volumes:
      - name: frontend-files
        configMap:
          name: frontend-files
---
apiVersion: v1
kind: Service
metadata:
  name: frontend-service
  namespace: trading-system
spec:
  selector:
    app: frontend
  ports:
  - port: 80
    targetPort: 80
  type: NodePort
EOF

kubectl apply -f kubernetes/frontend-deployment.yaml

# Get NodePort
kubectl get svc frontend-service -n trading-system
# Note the port (e.g., 30123)

# Access: http://192.168.1.100:30123
```

---

## 📦 Part 9: Verify Full System

**Step 1: Check All Pods**

```bash
kubectl get pods -n trading-system

# Should see all running:
# postgres-timeseries-xxx    1/1     Running
# redis-xxx                  1/1     Running
# trading-api-xxx            1/1     Running (3 replicas)
# airflow-webserver-xxx      1/1     Running
# airflow-scheduler-xxx      1/1     Running
# airflow-worker-xxx         1/1     Running (2 replicas)
# postgres-xxx               1/1     Running
# frontend-xxx               1/1     Running
```

**Step 2: Test API**

```bash
# From host machine
export VM_IP=192.168.1.100
export API_KEY=<your-api-key-from-secrets>

# Health check
curl http://$VM_IP:5000/api/health

# Test prediction (requires trained model - see next doc)
curl -X POST http://$VM_IP:5000/api/predict/trend-break \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "ticker": "AAPL",
    "start_date": "2023-01-01",
    "end_date": "2024-01-15"
  }'
```

**Step 3: Test Airflow**

```bash
# Access UI: http://$VM_IP:8080
# Login: admin / admin123

# Enable DAGs:
# 1. Click toggle to enable each DAG
# 2. Trigger manually with play button
# 3. View logs in Graph/Tree view
```

**Step 4: Test Frontend**

```bash
# Access: http://$VM_IP or http://$VM_IP:30123

# Update API key in browser console:
localStorage.setItem('apiKey', 'your-api-key')

# Test trend prediction form
```

**Step 5: Test Database**

```bash
# Connect to TimescaleDB
kubectl exec -it deployment/postgres-timeseries -n trading-system -- psql -U trading -d trading_data

# Check tables
\dt

# Query data (will be empty until models are trained)
SELECT COUNT(*) FROM stock_prices;
SELECT COUNT(*) FROM predictions_log;

\q
```

---

## 📦 Part 10: Monitoring & Logs

**View Logs**:

```bash
# API logs
kubectl logs -f deployment/trading-api -n trading-system

# Airflow scheduler logs
kubectl logs -f deployment/airflow-scheduler -n trading-system

# Airflow worker logs
kubectl logs -f deployment/airflow-worker -n trading-system

# PostgreSQL logs
kubectl logs -f deployment/postgres-timeseries -n trading-system

# All pods
kubectl logs -f -l app=trading-api -n trading-system --all-containers=true
```

**Resource Usage**:

```bash
# Pod resource usage
kubectl top pods -n trading-system

# Node resource usage
kubectl top nodes

# Describe pod (for troubleshooting)
kubectl describe pod <pod-name> -n trading-system
```

---

## 📦 Part 11: Useful Commands

**Restart Everything**:

```bash
# Restart all deployments
kubectl rollout restart deployment -n trading-system

# Restart specific deployment
kubectl rollout restart deployment/trading-api -n trading-system
```

**Update DAGs**:

```bash
# Update DAGs ConfigMap
kubectl create configmap airflow-dags \
  --from-file=kubernetes/airflow/dags/ \
  -n trading-system \
  --dry-run=client -o yaml | kubectl apply -f -

# Restart scheduler to pick up changes
kubectl rollout restart deployment/airflow-scheduler -n trading-system
```

**Scale Deployments**:

```bash
# Scale API
kubectl scale deployment trading-api --replicas=5 -n trading-system

# Scale workers
kubectl scale deployment airflow-worker --replicas=3 -n trading-system
```

**Backup Database**:

```bash
# Backup
kubectl exec deployment/postgres-timeseries -n trading-system -- \
  pg_dump -U trading trading_data > backup_$(date +%Y%m%d).sql

# Restore
kubectl exec -i deployment/postgres-timeseries -n trading-system -- \
  psql -U trading trading_data < backup_20240115.sql
```

**Stop Everything**:

```bash
# Delete all resources
kubectl delete namespace trading-system

# Stop minikube
minikube stop

# Stop port forwards
pkill -f "kubectl port-forward"
```

**Start Everything**:

```bash
# Start minikube
minikube start

# Deploy everything
cd trading-system
./deploy-all.sh  # Create this script with all kubectl apply commands
```

---

## 📦 Part 12: Create Deployment Script

**Create**: `deploy-all.sh`

```bash
#!/bin/bash
set -e

echo "Deploying Trading System to Kubernetes..."

# Namespace
kubectl apply -f kubernetes/namespace.yaml

# Secrets
kubectl apply -f kubernetes/secrets-local.yaml

# ConfigMaps
kubectl apply -f kubernetes/configmap.yaml

# Storage
kubectl apply -f kubernetes/persistent-volume.yaml

# Databases
echo "Deploying databases..."
kubectl apply -f kubernetes/postgres-timeseries-deployment.yaml
kubectl apply -f kubernetes/redis-deployment.yaml
kubectl apply -f kubernetes/airflow/airflow-postgres.yaml

# Wait for databases
kubectl wait --for=condition=ready pod -l app=postgres-timeseries -n trading-system --timeout=300s
kubectl wait --for=condition=ready pod -l app=redis -n trading-system --timeout=120s
kubectl wait --for=condition=ready pod -l app=postgres -n trading-system --timeout=300s

# API
echo "Deploying API..."
kubectl apply -f kubernetes/api-deployment.yaml
kubectl apply -f kubernetes/api-service.yaml

# Airflow DAGs
echo "Creating Airflow DAGs ConfigMap..."
kubectl create configmap airflow-dags \
  --from-file=kubernetes/airflow/dags/ \
  -n trading-system \
  --dry-run=client -o yaml | kubectl apply -f -

# Airflow
echo "Deploying Airflow..."
kubectl apply -f kubernetes/airflow/airflow-scheduler.yaml
kubectl apply -f kubernetes/airflow/airflow-deployment.yaml
kubectl apply -f kubernetes/airflow/airflow-worker.yaml
kubectl apply -f kubernetes/airflow/airflow-webserver-service.yaml

# Frontend
echo "Deploying Frontend..."
kubectl create configmap frontend-files \
  --from-file=frontend/ \
  -n trading-system \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f kubernetes/frontend-deployment.yaml

# Wait for everything
echo "Waiting for all pods to be ready..."
kubectl wait --for=condition=ready pod --all -n trading-system --timeout=600s

# Get service URLs
echo ""
echo "===================================="
echo "Deployment Complete!"
echo "===================================="
echo ""
echo "Services:"
echo "  API: http://$(minikube ip):$(kubectl get svc trading-api-service -n trading-system -o jsonpath='{.spec.ports[0].nodePort}')"
echo "  Airflow: http://$(minikube ip):8080"
echo "  Frontend: http://$(minikube ip):$(kubectl get svc frontend-service -n trading-system -o jsonpath='{.spec.ports[0].nodePort}')"
echo ""
echo "Port Forwards (run in separate terminal):"
echo "  kubectl port-forward svc/trading-api-service 5000:5000 -n trading-system --address=0.0.0.0"
echo "  kubectl port-forward svc/airflow-webserver 8080:8080 -n trading-system --address=0.0.0.0"
echo ""
echo "Check status:"
echo "  kubectl get pods -n trading-system"
echo ""
```

```bash
# Make executable
chmod +x deploy-all.sh

# Run
./deploy-all.sh
```

---

## ✅ Verification Checklist

After deployment, verify:

- [ ] All pods running: `kubectl get pods -n trading-system`
- [ ] API health check: `curl http://VM_IP:5000/api/health`
- [ ] Airflow UI accessible: http://VM_IP:8080
- [ ] Frontend accessible: http://VM_IP
- [ ] Database tables created: `kubectl exec -it deployment/postgres-timeseries -n trading-system -- psql -U trading -d trading_data -c "\dt"`
- [ ] Redis working: `kubectl exec -it deployment/redis -n trading-system -- redis-cli ping`
- [ ] Airflow DAGs visible in UI
- [ ] API can connect to database
- [ ] Frontend can call API

---

## 🐛 Troubleshooting

**Pods not starting**:
```bash
kubectl describe pod <pod-name> -n trading-system
kubectl logs <pod-name> -n trading-system
```

**Out of memory**:
```bash
# Increase VM RAM to 12GB or 16GB
# Or reduce resource requests in deployments
```

**Cannot access from host**:
```bash
# Check VM IP
ip addr show

# Check port forwards are running
ps aux | grep "kubectl port-forward"

# Check firewall (allow ports 5000, 8080, 80)
sudo ufw allow 5000
sudo ufw allow 8080
sudo ufw allow 80
```

**Database connection errors**:
```bash
# Check postgres is running
kubectl get pods -l app=postgres-timeseries -n trading-system

# Check secrets
kubectl get secret trading-secrets -n trading-system -o yaml
```

---

## 🎯 Next Steps

Once deployed, proceed to:
1. **[MODEL_TRAINING_GUIDE.md](MODEL_TRAINING_GUIDE.md)** - Train models on S&P 500, Bitcoin, Ethereum
2. **[STARTUP_PITCH_CHECKLIST.md](STARTUP_PITCH_CHECKLIST.md)** - Turn this into a startup

---

## 📚 Quick Reference

**Essential Commands**:
```bash
# Status
kubectl get pods -n trading-system
kubectl get svc -n trading-system
kubectl top pods -n trading-system

# Logs
kubectl logs -f deployment/trading-api -n trading-system

# Port Forwards
kubectl port-forward svc/trading-api-service 5000:5000 -n trading-system --address=0.0.0.0 &
kubectl port-forward svc/airflow-webserver 8080:8080 -n trading-system --address=0.0.0.0 &

# Restart
kubectl rollout restart deployment/trading-api -n trading-system

# Shell into pod
kubectl exec -it deployment/trading-api -n trading-system -- /bin/bash

# Delete everything
kubectl delete namespace trading-system
```

**URLs** (replace VM_IP with your VM's IP):
- API: http://VM_IP:5000
- Airflow: http://VM_IP:8080
- Frontend: http://VM_IP

Good luck! 🚀
