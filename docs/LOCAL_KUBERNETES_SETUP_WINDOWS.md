# Run Trading System on Windows with Docker Desktop + Kubernetes

Complete guide to run your entire trading system (Airflow, PostgreSQL, API, Frontend) on Windows using Docker Desktop's built-in Kubernetes - NO VM required.

---

## 🎯 Architecture Overview

**What we're building:**
```
Windows 10/11
└── Docker Desktop
    └── Kubernetes (built-in)
        ├── PostgreSQL + TimescaleDB (database)
        ├── Redis (cache)
        ├── Airflow (scheduler, webserver, workers)
        ├── Flask API (trading predictions)
        └── Frontend (web interface)
```

**Why this is better than VM:**
- ✅ Uses less RAM (no full Ubuntu OS running)
- ✅ Faster startup (containers vs full OS boot)
- ✅ Easier to manage (Docker Desktop GUI)
- ✅ Production-like setup (same as cloud deployment)
- ✅ You already have all the Kubernetes files created!

---

## 📋 Prerequisites

### Step 1: Install Docker Desktop (10 minutes)

**Download:**
1. Go to: https://www.docker.com/products/docker-desktop/
2. Click **Download for Windows**
3. Run installer: `Docker Desktop Installer.exe`

**Installation:**
1. Check: ☑️ **Use WSL 2 instead of Hyper-V** (recommended)
2. Click **OK**
3. Wait for installation (5 minutes)
4. Click **Close and restart** when prompted
5. Computer restarts

**After restart:**
1. Docker Desktop opens automatically
2. Accept terms and conditions
3. Skip tutorial (or watch it, 2 minutes)

**Verify Docker is running:**
1. Open **PowerShell**
2. Run:
```powershell
docker --version
```
Should show: `Docker version 24.x.x`

3. Run:
```powershell
docker run hello-world
```
Should download and run a test container

---

### Step 2: Enable Kubernetes in Docker Desktop (5 minutes)

**Enable Kubernetes:**
1. Right-click **Docker Desktop icon** in system tray (bottom-right)
2. Click **Settings**
3. Click **Kubernetes** in left sidebar
4. Check: ☑️ **Enable Kubernetes**
5. Click **Apply & Restart**
6. Wait 3-5 minutes (downloads Kubernetes components)
7. When done, you'll see: **Kubernetes is running** (green dot)

**Verify Kubernetes:**
Open PowerShell:
```powershell
kubectl version --client
kubectl cluster-info
```

Should show Kubernetes is running at localhost

---

### Step 3: Install kubectl (if not included)

**Check if already installed:**
```powershell
kubectl version --client
```

**If not found, install:**

**Option 1: Using Chocolatey (easiest)**
```powershell
# Install Chocolatey first (if you don't have it)
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# Install kubectl
choco install kubernetes-cli
```

**Option 2: Manual download**
1. Download: https://kubernetes.io/docs/tasks/tools/install-kubectl-windows/
2. Add to PATH

---

## 🚀 Deploy Your Trading System

### Phase 1: Prepare Your Project Files (5 minutes)

**Navigate to your project:**
```powershell
cd C:\Users\nicho\OneDrive\Desktop\code\Securities_prediction_model
```

**Verify you have these directories:**
```powershell
ls kubernetes/
ls SP_historical_data.py
ls frontend/
```

**You should see:**
- `kubernetes/` folder with all .yaml files
- `SP_historical_data.py` (your main Python script)
- `frontend/` folder with HTML/CSS/JS

---

### Phase 2: Build Docker Images (10 minutes)

**You need to create Dockerfiles if you don't have them.**

#### Create Dockerfile for Flask API

**Create file: `Dockerfile`**

```powershell
New-Item -Path . -Name "Dockerfile" -ItemType "file"
code Dockerfile  # or notepad Dockerfile
```

**Paste this:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY SP_historical_data.py .
COPY models/ ./models/

# Expose port
EXPOSE 5000

# Run Flask API
CMD ["python", "SP_historical_data.py"]
```

**Save and close**

---

#### Create requirements.txt

**Create file: `requirements.txt`**

```powershell
New-Item -Path . -Name "requirements.txt" -ItemType "file"
code requirements.txt
```

**Paste this (adjust based on your actual dependencies):**
```txt
flask==3.0.0
flask-cors==4.0.0
pandas==2.1.4
numpy==1.26.2
scikit-learn==1.3.2
xgboost==2.0.3
tensorflow==2.15.0
psycopg2-binary==2.9.9
sqlalchemy==2.0.23
yfinance==0.2.33
python-dotenv==1.0.0
requests==2.31.0
```

**Save and close**

---

#### Build the Docker Image

```powershell
docker build -t trading-api:latest .
```

**This will:**
- Download Python base image
- Install dependencies
- Package your code
- Takes 5-10 minutes first time

**Verify image was created:**
```powershell
docker images
```
Should see: `trading-api` with tag `latest`

---

### Phase 3: Deploy to Kubernetes (10 minutes)

**Apply all Kubernetes manifests:**

```powershell
# Create namespace (optional, organizes resources)
kubectl create namespace trading-system

# Deploy PostgreSQL + TimescaleDB
kubectl apply -f kubernetes/postgres-pvc.yaml
kubectl apply -f kubernetes/postgres-deployment.yaml
kubectl apply -f kubernetes/postgres-service.yaml

# Deploy Redis
kubectl apply -f kubernetes/redis-deployment.yaml
kubectl apply -f kubernetes/redis-service.yaml

# Deploy Flask API
kubectl apply -f kubernetes/api-deployment.yaml
kubectl apply -f kubernetes/api-service.yaml
kubectl apply -f kubernetes/api-hpa.yaml

# Deploy Airflow
kubectl apply -f kubernetes/airflow-postgres.yaml
kubectl apply -f kubernetes/airflow-scheduler.yaml
kubectl apply -f kubernetes/airflow-webserver.yaml
kubectl apply -f kubernetes/airflow-worker.yaml

# Deploy Frontend
kubectl apply -f kubernetes/frontend-deployment.yaml
kubectl apply -f kubernetes/frontend-service.yaml
```

**Wait for pods to be ready (2-3 minutes):**
```powershell
kubectl get pods --watch
```

Press **Ctrl+C** when all pods show `Running` status

---

### Phase 4: Access Your Services (2 minutes)

**Port forwarding to access services on localhost:**

**Open separate PowerShell windows for each:**

**Window 1: Flask API**
```powershell
kubectl port-forward service/trading-api 5000:5000
```
Access at: http://localhost:5000

---

**Window 2: Airflow Web UI**
```powershell
kubectl port-forward service/airflow-webserver 8080:8080
```
Access at: http://localhost:8080
- Username: `admin`
- Password: `admin` (or whatever you set in airflow config)

---

**Window 3: Frontend**
```powershell
kubectl port-forward service/frontend 8080:80
```
Access at: http://localhost:8080

**Note:** If port 8080 conflicts (Airflow), use different port:
```powershell
kubectl port-forward service/frontend 3000:80
```
Access at: http://localhost:3000

---

**Window 4: PostgreSQL (for debugging)**
```powershell
kubectl port-forward service/postgres 5432:5432
```

Connect with:
- Host: `localhost`
- Port: `5432`
- Database: `trading_db`
- User: `postgres`
- Password: (from your postgres deployment yaml)

---

## 🔧 Troubleshooting

### Issue 1: Pod Shows "ImagePullBackOff"

**Cause:** Kubernetes can't find your Docker image

**Fix:**
```powershell
# Load image into Docker Desktop's Kubernetes
docker build -t trading-api:latest .

# Check if image exists
docker images | findstr trading-api

# If using minikube instead (you're not, but just in case):
# minikube image load trading-api:latest
```

**Update deployment to use local image:**

Edit `kubernetes/api-deployment.yaml`:
```yaml
spec:
  containers:
  - name: trading-api
    image: trading-api:latest
    imagePullPolicy: Never  # ← Add this line (or change to IfNotPresent)
```

Reapply:
```powershell
kubectl apply -f kubernetes/api-deployment.yaml
```

---

### Issue 2: Pod Shows "CrashLoopBackOff"

**Cause:** Container starts then immediately crashes

**Check logs:**
```powershell
# List pods
kubectl get pods

# View logs (replace pod-name with actual name)
kubectl logs <pod-name>

# Example:
kubectl logs trading-api-7d9f8c6b5-xk2mq
```

**Common causes:**
- Missing environment variables
- Database connection failed
- Python import errors
- Port already in use

**Fix environment variables:**

Edit deployment yaml to add env vars:
```yaml
env:
- name: DATABASE_URL
  value: "postgresql://postgres:password@postgres:5432/trading_db"
- name: REDIS_URL
  value: "redis://redis:6379/0"
- name: FLASK_ENV
  value: "production"
```

---

### Issue 3: Can't Connect to Database

**Check if PostgreSQL is running:**
```powershell
kubectl get pods | findstr postgres
```

Should show: `postgres-xxxxx  1/1  Running`

**If not running, check logs:**
```powershell
kubectl logs <postgres-pod-name>
```

**Common fix - Create database manually:**
```powershell
# Connect to postgres pod
kubectl exec -it <postgres-pod-name> -- psql -U postgres

# Inside psql:
CREATE DATABASE trading_db;
\c trading_db
CREATE EXTENSION IF NOT EXISTS timescaledb;
\q
```

---

### Issue 4: Port Forward Stops Working

**Cause:** Port forward sessions timeout or you closed window

**Fix:** Just run port-forward command again

**Persistent solution - Use LoadBalancer service (Docker Desktop supports it):**

Edit `kubernetes/api-service.yaml`:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: trading-api
spec:
  type: LoadBalancer  # ← Change from ClusterIP to LoadBalancer
  ports:
  - port: 5000
    targetPort: 5000
  selector:
    app: trading-api
```

Apply:
```powershell
kubectl apply -f kubernetes/api-service.yaml
```

Get external IP:
```powershell
kubectl get svc trading-api
```

Access directly at: `http://localhost:5000` (Docker Desktop maps LoadBalancer to localhost)

---

## 📊 Monitoring & Management

### View All Resources

```powershell
# All pods
kubectl get pods

# All services
kubectl get services

# All deployments
kubectl get deployments

# Everything
kubectl get all
```

---

### View Logs

```powershell
# View logs for specific pod
kubectl logs <pod-name>

# Follow logs (live tail)
kubectl logs -f <pod-name>

# View last 100 lines
kubectl logs --tail=100 <pod-name>

# View logs from all pods of a deployment
kubectl logs -l app=trading-api
```

---

### Execute Commands in Pod

```powershell
# Open shell in pod
kubectl exec -it <pod-name> -- /bin/bash

# Run one-off command
kubectl exec <pod-name> -- python --version

# Connect to PostgreSQL
kubectl exec -it <postgres-pod-name> -- psql -U postgres -d trading_db
```

---

### Scale Deployments

```powershell
# Scale API to 3 replicas
kubectl scale deployment trading-api --replicas=3

# Verify
kubectl get pods
```

---

### Restart Deployment (when you update code)

```powershell
# Rebuild Docker image
docker build -t trading-api:latest .

# Restart deployment (forces pull new image)
kubectl rollout restart deployment/trading-api

# Watch rollout status
kubectl rollout status deployment/trading-api
```

---

### Delete Everything

```powershell
# Delete specific deployment
kubectl delete deployment trading-api

# Delete all resources in namespace
kubectl delete namespace trading-system

# Or delete everything one by one
kubectl delete -f kubernetes/api-deployment.yaml
kubectl delete -f kubernetes/postgres-deployment.yaml
# ... etc
```

---

## 💡 Development Workflow

### Typical workflow when developing:

**1. Make code changes to `SP_historical_data.py`**

**2. Rebuild Docker image:**
```powershell
docker build -t trading-api:latest .
```

**3. Restart deployment:**
```powershell
kubectl rollout restart deployment/trading-api
```

**4. Check logs:**
```powershell
kubectl logs -f -l app=trading-api
```

**5. Test at `http://localhost:5000`**

---

## 🎯 Quick Start Script

**Create a PowerShell script to automate deployment:**

**Create file: `deploy.ps1`**

```powershell
# deploy.ps1 - Quick deployment script

Write-Host "Building Docker image..." -ForegroundColor Green
docker build -t trading-api:latest .

Write-Host "Applying Kubernetes manifests..." -ForegroundColor Green
kubectl apply -f kubernetes/postgres-pvc.yaml
kubectl apply -f kubernetes/postgres-deployment.yaml
kubectl apply -f kubernetes/postgres-service.yaml
kubectl apply -f kubernetes/redis-deployment.yaml
kubectl apply -f kubernetes/redis-service.yaml
kubectl apply -f kubernetes/api-deployment.yaml
kubectl apply -f kubernetes/api-service.yaml
kubectl apply -f kubernetes/airflow-postgres.yaml
kubectl apply -f kubernetes/airflow-scheduler.yaml
kubectl apply -f kubernetes/airflow-webserver.yaml
kubectl apply -f kubernetes/airflow-worker.yaml
kubectl apply -f kubernetes/frontend-deployment.yaml
kubectl apply -f kubernetes/frontend-service.yaml

Write-Host "Waiting for pods to be ready..." -ForegroundColor Green
kubectl wait --for=condition=ready pod -l app=trading-api --timeout=300s
kubectl wait --for=condition=ready pod -l app=postgres --timeout=300s

Write-Host "Deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Port forward commands:" -ForegroundColor Yellow
Write-Host "  API:      kubectl port-forward service/trading-api 5000:5000"
Write-Host "  Airflow:  kubectl port-forward service/airflow-webserver 8080:8080"
Write-Host "  Frontend: kubectl port-forward service/frontend 3000:80"
```

**Run it:**
```powershell
.\deploy.ps1
```

---

## 🔄 Update Deployment Script

**Create file: `update.ps1`**

```powershell
# update.ps1 - Rebuild and restart after code changes

param(
    [string]$service = "api"
)

Write-Host "Rebuilding Docker image..." -ForegroundColor Green
docker build -t trading-api:latest .

Write-Host "Restarting deployment..." -ForegroundColor Green
if ($service -eq "api") {
    kubectl rollout restart deployment/trading-api
} elseif ($service -eq "airflow") {
    kubectl rollout restart deployment/airflow-scheduler
    kubectl rollout restart deployment/airflow-webserver
    kubectl rollout restart deployment/airflow-worker
}

Write-Host "Watching rollout..." -ForegroundColor Green
kubectl rollout status deployment/trading-$service

Write-Host "Deployment updated!" -ForegroundColor Green
```

**Use it:**
```powershell
# Update API
.\update.ps1 -service api

# Update Airflow
.\update.ps1 -service airflow
```

---

## 📦 Database Initialization

**Create database tables and extensions:**

**Create file: `init-db.ps1`**

```powershell
# init-db.ps1 - Initialize database

Write-Host "Finding PostgreSQL pod..." -ForegroundColor Green
$POD = kubectl get pods -l app=postgres -o jsonpath='{.items[0].metadata.name}'

Write-Host "Connecting to PostgreSQL pod: $POD" -ForegroundColor Green

Write-Host "Creating database and extensions..." -ForegroundColor Green
kubectl exec -it $POD -- psql -U postgres -c "CREATE DATABASE IF NOT EXISTS trading_db;"
kubectl exec -it $POD -- psql -U postgres -d trading_db -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

Write-Host "Running SQL schema..." -ForegroundColor Green
# If you have a schema.sql file:
# kubectl exec -i $POD -- psql -U postgres -d trading_db < schema.sql

Write-Host "Database initialized!" -ForegroundColor Green
```

**Run it:**
```powershell
.\init-db.ps1
```

---

## 🌐 Access Services - Summary

**After everything is deployed:**

| Service | Port Forward Command | URL |
|---------|---------------------|-----|
| **Flask API** | `kubectl port-forward svc/trading-api 5000:5000` | http://localhost:5000 |
| **Airflow** | `kubectl port-forward svc/airflow-webserver 8080:8080` | http://localhost:8080 |
| **Frontend** | `kubectl port-forward svc/frontend 3000:80` | http://localhost:3000 |
| **PostgreSQL** | `kubectl port-forward svc/postgres 5432:5432` | localhost:5432 |
| **Redis** | `kubectl port-forward svc/redis 6379:6379` | localhost:6379 |

---

## ✅ Verification Checklist

**Confirm everything is working:**

- [ ] Docker Desktop is running (green icon in system tray)
- [ ] Kubernetes enabled in Docker Desktop
- [ ] `kubectl get nodes` shows 1 node ready
- [ ] `docker images` shows `trading-api:latest`
- [ ] `kubectl get pods` shows all pods in `Running` status
- [ ] `kubectl get services` shows all services created
- [ ] Can access http://localhost:5000/api/health (or similar endpoint)
- [ ] Can access http://localhost:8080 (Airflow UI)
- [ ] Can access http://localhost:3000 (Frontend)

---

## 🚀 Next Steps After Setup

**1. Initialize Database:**
```powershell
.\init-db.ps1
```

**2. Train Models (follow MODEL_TRAINING_GUIDE.md):**
```powershell
python scripts/train_meta_learning.py
python scripts/train_trend_break.py
```

**3. Start Airflow DAGs:**
- Open http://localhost:8080
- Enable DAGs for S&P 500 hourly, crypto 10-min, etc.

**4. Test API:**
```powershell
curl http://localhost:5000/api/predict/trend-break -X POST -H "Content-Type: application/json" -d '{\"ticker\":\"AAPL\",\"prediction_date\":\"2026-01-20\"}'
```

**5. Access Frontend:**
- Open http://localhost:3000
- Test trend break prediction
- Test options analysis

---

## 💾 Resource Usage

**Expected RAM usage:**
- Docker Desktop: 2-4 GB
- PostgreSQL: 200-500 MB
- Redis: 50-100 MB
- Airflow (all components): 1-2 GB
- Flask API: 200-500 MB
- Frontend: 50 MB
- **Total: 4-8 GB** (much less than VM!)

**Expected CPU:**
- Idle: 5-10%
- During model training: 50-100%
- During predictions: 20-40%

---

## 🎯 Comparison: VM vs Docker Desktop

| Aspect | Ubuntu VM | Docker Desktop + K8s |
|--------|-----------|---------------------|
| **RAM Usage** | 4-8 GB | 4-8 GB |
| **Disk Space** | 25-50 GB | 10-20 GB |
| **Boot Time** | 30-60 sec | 5-10 sec |
| **Ease of Use** | Moderate | Easy |
| **Windows Integration** | Poor | Excellent |
| **Production-like** | Less | More |
| **Your files** | Already created! | Already created! ✅ |

**Winner:** Docker Desktop + Kubernetes (and you have all the files ready!)

---

## 📚 Additional Resources

**Docker Desktop:**
- Official docs: https://docs.docker.com/desktop/windows/
- Kubernetes in Docker Desktop: https://docs.docker.com/desktop/kubernetes/

**Kubectl:**
- Cheat sheet: https://kubernetes.io/docs/reference/kubectl/cheatsheet/

**Troubleshooting:**
- Docker Desktop logs: Click whale icon → Troubleshoot → Show logs
- Kubernetes Dashboard: https://kubernetes.io/docs/tasks/access-application-cluster/web-ui-dashboard/

---

## 🚀 Summary

**What you're doing:**
1. Install Docker Desktop (10 min)
2. Enable Kubernetes (5 min)
3. Build Docker image for your Flask API (10 min)
4. Deploy everything with `kubectl apply` (5 min)
5. Port-forward to access services (1 min)

**Total time:** 30-40 minutes

**Benefits:**
- ✅ No VM needed (saves RAM)
- ✅ Uses your existing Kubernetes files (no rewriting)
- ✅ Production-like setup
- ✅ Easy to manage with Docker Desktop GUI
- ✅ Fast rebuild/redeploy cycle

**You're ready to run your entire trading system on Windows!**

---

*Guide created: January 17, 2026*
*Platform: Docker Desktop + Kubernetes on Windows 10/11*
*No VM required*
