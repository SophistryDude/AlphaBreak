# deploy-local.ps1
# =================
# Deploy Trading Prediction API to local Docker Desktop Kubernetes
#
# Usage:
#   .\deploy-local.ps1           # Full deployment
#   .\deploy-local.ps1 -SkipBuild  # Skip Docker build
#   .\deploy-local.ps1 -Reset      # Delete and redeploy everything

param(
    [switch]$SkipBuild,
    [switch]$Reset,
    [switch]$Help
)

if ($Help) {
    Write-Host @"
Trading Prediction API - Local Kubernetes Deployment

Usage:
    .\deploy-local.ps1              Full deployment (build + deploy)
    .\deploy-local.ps1 -SkipBuild   Skip Docker image build
    .\deploy-local.ps1 -Reset       Delete everything and redeploy

Requirements:
    - Docker Desktop with Kubernetes enabled
    - kubectl configured to use docker-desktop context
"@
    exit 0
}

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Trading Prediction API - Local Deploy" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check prerequisites
Write-Host "Checking prerequisites..." -ForegroundColor Yellow

# Check Docker
try {
    $dockerVersion = docker --version
    Write-Host "  [OK] Docker: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "  [ERROR] Docker not found. Please install Docker Desktop." -ForegroundColor Red
    exit 1
}

# Check kubectl
try {
    $kubectlVersion = kubectl version --client --short 2>$null
    Write-Host "  [OK] kubectl: $kubectlVersion" -ForegroundColor Green
} catch {
    Write-Host "  [ERROR] kubectl not found. Please install kubectl." -ForegroundColor Red
    exit 1
}

# Check Kubernetes context
$context = kubectl config current-context
if ($context -ne "docker-desktop") {
    Write-Host "  [WARN] Current context is '$context', switching to 'docker-desktop'..." -ForegroundColor Yellow
    kubectl config use-context docker-desktop
}
Write-Host "  [OK] Kubernetes context: docker-desktop" -ForegroundColor Green

# Check cluster is running
try {
    kubectl cluster-info | Out-Null
    Write-Host "  [OK] Kubernetes cluster is running" -ForegroundColor Green
} catch {
    Write-Host "  [ERROR] Kubernetes cluster not running. Enable it in Docker Desktop settings." -ForegroundColor Red
    exit 1
}

Write-Host ""

# Reset if requested
if ($Reset) {
    Write-Host "Resetting deployment..." -ForegroundColor Yellow
    kubectl delete namespace trading-system --ignore-not-found=true 2>$null
    kubectl delete pv trading-models-pv --ignore-not-found=true 2>$null
    kubectl delete pv trading-logs-pv --ignore-not-found=true 2>$null
    kubectl delete storageclass local-storage --ignore-not-found=true 2>$null
    Write-Host "  [OK] Previous deployment deleted" -ForegroundColor Green
    Write-Host ""
}

# Create directories if they don't exist
Write-Host "Creating local directories..." -ForegroundColor Yellow
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $projectRoot) { $projectRoot = $PWD }

$modelsDir = Join-Path $projectRoot "models"
$logsDir = Join-Path $projectRoot "logs"

if (-not (Test-Path $modelsDir)) {
    New-Item -ItemType Directory -Path $modelsDir -Force | Out-Null
    Write-Host "  [OK] Created: $modelsDir" -ForegroundColor Green
} else {
    Write-Host "  [OK] Exists: $modelsDir" -ForegroundColor Green
}

if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
    Write-Host "  [OK] Created: $logsDir" -ForegroundColor Green
} else {
    Write-Host "  [OK] Exists: $logsDir" -ForegroundColor Green
}

Write-Host ""

# Build Docker image
if (-not $SkipBuild) {
    Write-Host "Building Docker image..." -ForegroundColor Yellow
    Write-Host "  This may take a few minutes on first build..." -ForegroundColor Gray

    docker build -f flask_app/Dockerfile -t trading-api:latest .

    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [ERROR] Docker build failed" -ForegroundColor Red
        exit 1
    }
    Write-Host "  [OK] Image built: trading-api:latest" -ForegroundColor Green
} else {
    Write-Host "Skipping Docker build (using existing image)..." -ForegroundColor Yellow
}

Write-Host ""

# Apply Kubernetes manifests
Write-Host "Applying Kubernetes manifests..." -ForegroundColor Yellow

# 1. Namespace
Write-Host "  Applying namespace..." -ForegroundColor Gray
kubectl apply -f kubernetes/namespace.yaml
Write-Host "  [OK] Namespace: trading-system" -ForegroundColor Green

# 2. Storage class and persistent volumes
Write-Host "  Applying storage..." -ForegroundColor Gray
kubectl apply -f kubernetes/persistent-volume.yaml
Write-Host "  [OK] Persistent volumes created" -ForegroundColor Green

# 3. ConfigMap
Write-Host "  Applying configmap..." -ForegroundColor Gray
kubectl apply -f kubernetes/configmap.yaml
Write-Host "  [OK] ConfigMap: trading-api-config" -ForegroundColor Green

# 4. Secrets
Write-Host "  Applying secrets..." -ForegroundColor Gray
kubectl apply -f kubernetes/secrets.yaml
Write-Host "  [OK] Secrets: trading-secrets" -ForegroundColor Green

# 5. Redis
Write-Host "  Deploying Redis..." -ForegroundColor Gray
kubectl apply -f kubernetes/redis-deployment.yaml
Write-Host "  [OK] Redis deployed" -ForegroundColor Green

# 6. API Deployment
Write-Host "  Deploying Trading API..." -ForegroundColor Gray
kubectl apply -f kubernetes/api-deployment.yaml
Write-Host "  [OK] Trading API deployed" -ForegroundColor Green

# 7. API Service
Write-Host "  Creating API service..." -ForegroundColor Gray
kubectl apply -f kubernetes/api-service.yaml
Write-Host "  [OK] Service: trading-api-service (LoadBalancer)" -ForegroundColor Green

Write-Host ""

# Wait for pods to be ready
Write-Host "Waiting for pods to be ready..." -ForegroundColor Yellow
Write-Host "  (This may take 1-2 minutes)" -ForegroundColor Gray

# Wait for Redis
kubectl wait --for=condition=ready pod -l app=redis -n trading-system --timeout=120s 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  [OK] Redis is ready" -ForegroundColor Green
} else {
    Write-Host "  [WARN] Redis not ready yet, continuing..." -ForegroundColor Yellow
}

# Wait for API
kubectl wait --for=condition=ready pod -l app=trading-api -n trading-system --timeout=180s 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  [OK] Trading API is ready" -ForegroundColor Green
} else {
    Write-Host "  [WARN] API not ready yet. Check logs with: kubectl logs -l app=trading-api -n trading-system" -ForegroundColor Yellow
}

Write-Host ""

# Get service info
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deployment Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Show pod status
Write-Host "Pod Status:" -ForegroundColor Yellow
kubectl get pods -n trading-system

Write-Host ""
Write-Host "Service Status:" -ForegroundColor Yellow
kubectl get svc -n trading-system

Write-Host ""
Write-Host "Access URLs:" -ForegroundColor Yellow
Write-Host "  API:          http://localhost:5000" -ForegroundColor White
Write-Host "  Health Check: http://localhost:5000/api/health" -ForegroundColor White
Write-Host "  API Status:   http://localhost:5000/api/status" -ForegroundColor White

Write-Host ""
Write-Host "Useful Commands:" -ForegroundColor Yellow
Write-Host "  View logs:     kubectl logs -f -l app=trading-api -n trading-system" -ForegroundColor Gray
Write-Host "  View pods:     kubectl get pods -n trading-system" -ForegroundColor Gray
Write-Host "  Restart API:   kubectl rollout restart deployment/trading-api -n trading-system" -ForegroundColor Gray
Write-Host "  Delete all:    kubectl delete namespace trading-system" -ForegroundColor Gray

Write-Host ""
Write-Host "Test the API:" -ForegroundColor Yellow
Write-Host '  curl http://localhost:5000/api/health' -ForegroundColor Gray
Write-Host '  curl -X POST http://localhost:5000/api/predict -H "Content-Type: application/json" -d "{\"ticker\":\"AAPL\"}"' -ForegroundColor Gray
