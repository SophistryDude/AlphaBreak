# AlphaBreak Complete Kubernetes Manifest List

All Kubernetes files for deploying AlphaBreak with scheduling capabilities.

## Core Infrastructure

### Namespace & Configuration
- [namespace.yaml](namespace.yaml) - Isolated namespace for the trading system
- [configmap.yaml](configmap.yaml) - Environment variables and configuration
- [secrets.yaml](secrets.yaml) - API keys and credentials (UPDATE BEFORE DEPLOYING!)
- [persistent-volume.yaml](persistent-volume.yaml) - Storage for models and logs

### Storage
- **Models Storage**: 10Gi ReadWriteMany PVC for trained models
- **Logs Storage**: 5Gi ReadWriteMany PVC for application logs
- **Postgres Storage**: 5Gi ReadWriteOnce PVC for Airflow metadata

## Application Components

### Trading API
- [api-deployment.yaml](api-deployment.yaml) - Flask API deployment (3 replicas)
  - `/api/health` - Health check endpoint
  - `/api/predict/trend-break` - Trend break prediction
  - `/api/predict/options` - Options analysis
- [api-service.yaml](api-service.yaml) - ClusterIP service on port 5000
- [api-hpa.yaml](api-hpa.yaml) - Horizontal Pod Autoscaler (2-10 replicas)
- [ingress.yaml](ingress.yaml) - External access with SSL/TLS

### Caching
- [redis-deployment.yaml](redis-deployment.yaml) - Redis for rate limiting and caching

## Scheduling Options

### Option 1: CronJobs (Simpler)
Located in `cronjobs/`:
- [indicator-analysis-cronjob.yaml](cronjobs/indicator-analysis-cronjob.yaml) - Daily at 2 AM
- [model-retraining-cronjob.yaml](cronjobs/model-retraining-cronjob.yaml) - Weekly Sunday at 3 AM
- [backtest-cronjob.yaml](cronjobs/backtest-cronjob.yaml) - Monthly 1st at 4 AM

### Option 2: Apache Airflow (Recommended)
Located in `airflow/`:

**Airflow Infrastructure:**
- [airflow-deployment.yaml](airflow/airflow-deployment.yaml) - Airflow webserver
- [airflow-scheduler.yaml](airflow/airflow-scheduler.yaml) - Airflow scheduler
- [airflow-worker.yaml](airflow/airflow-worker.yaml) - Celery workers (2 replicas)
- [airflow-postgres.yaml](airflow/airflow-postgres.yaml) - PostgreSQL for metadata
- [airflow-webserver-service.yaml](airflow/airflow-webserver-service.yaml) - LoadBalancer service
- [values.yaml](airflow/values.yaml) - Helm chart values (if using Helm)

**Airflow DAGs:**
- [dags/model_retraining_dag.py](airflow/dags/model_retraining_dag.py) - 7-step model retraining pipeline
- [dags/indicator_analysis_dag.py](airflow/dags/indicator_analysis_dag.py) - Daily indicator analysis
- [dags/backtest_dag.py](airflow/dags/backtest_dag.py) - Monthly backtesting

## Deployment Order

### Quick Start (CronJobs)
```bash
# 1. Core infrastructure
kubectl apply -f namespace.yaml
kubectl apply -f secrets.yaml  # UPDATE FIRST!
kubectl apply -f configmap.yaml
kubectl apply -f persistent-volume.yaml

# 2. Dependencies
kubectl apply -f redis-deployment.yaml

# 3. API
kubectl apply -f api-deployment.yaml
kubectl apply -f api-service.yaml
kubectl apply -f api-hpa.yaml
kubectl apply -f ingress.yaml

# 4. Scheduling
kubectl apply -f cronjobs/
```

### Production (Airflow via Kubernetes Manifests)
```bash
# 1-3. Same as above

# 4. Airflow infrastructure
kubectl apply -f airflow/airflow-postgres.yaml
kubectl apply -f airflow/airflow-deployment.yaml
kubectl apply -f airflow/airflow-scheduler.yaml
kubectl apply -f airflow/airflow-worker.yaml
kubectl apply -f airflow/airflow-webserver-service.yaml

# 5. Deploy DAGs (create ConfigMap)
kubectl create configmap airflow-dags \
  --from-file=airflow/dags/ \
  -n trading-system
```

### Production (Airflow via Helm - Recommended)
```bash
# 1-3. Same as core infrastructure

# 4. Install Airflow with Helm
helm repo add apache-airflow https://airflow.apache.org
helm repo update

helm install airflow apache-airflow/airflow \
  --namespace trading-system \
  -f airflow/values.yaml

# 5. Deploy custom DAGs
kubectl create configmap airflow-dags \
  --from-file=airflow/dags/ \
  -n trading-system
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Kubernetes Cluster                      │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                 Namespace: trading-system              │  │
│  │                                                         │  │
│  │  ┌──────────────┐     ┌──────────────┐                │  │
│  │  │   Ingress    │────▶│  Trading API │                │  │
│  │  │  (SSL/TLS)   │     │  (3 replicas)│                │  │
│  │  └──────────────┘     └──────┬───────┘                │  │
│  │                              │                          │  │
│  │                              ▼                          │  │
│  │                       ┌──────────────┐                 │  │
│  │                       │    Redis     │                 │  │
│  │                       │   (Cache)    │                 │  │
│  │                       └──────────────┘                 │  │
│  │                                                         │  │
│  │  ┌─────────────── Scheduling ─────────────────┐       │  │
│  │  │                                              │       │  │
│  │  │  Option 1: CronJobs                         │       │  │
│  │  │  ├─ Indicator Analysis (Daily 2 AM)         │       │  │
│  │  │  ├─ Model Retraining (Weekly Sun 3 AM)      │       │  │
│  │  │  └─ Backtest (Monthly 1st, 4 AM)            │       │  │
│  │  │                                              │       │  │
│  │  │  Option 2: Apache Airflow (Recommended)     │       │  │
│  │  │  ┌────────────┐  ┌────────────┐             │       │  │
│  │  │  │ Webserver  │  │ Scheduler  │             │       │  │
│  │  │  └────────────┘  └────────────┘             │       │  │
│  │  │  ┌────────────┐  ┌────────────┐             │       │  │
│  │  │  │ Worker 1   │  │ Worker 2   │             │       │  │
│  │  │  └────────────┘  └────────────┘             │       │  │
│  │  │        │               │                     │       │  │
│  │  │        └───────┬───────┘                     │       │  │
│  │  │                ▼                             │       │  │
│  │  │         ┌──────────────┐                     │       │  │
│  │  │         │  PostgreSQL  │                     │       │  │
│  │  │         │  (Metadata)  │                     │       │  │
│  │  │         └──────────────┘                     │       │  │
│  │  └──────────────────────────────────────────────┘       │  │
│  │                                                         │  │
│  │  ┌─────────────── Storage ─────────────────┐           │  │
│  │  │  ┌──────────────┐  ┌──────────────┐    │           │  │
│  │  │  │    Models    │  │     Logs     │    │           │  │
│  │  │  │   (10 Gi)    │  │    (5 Gi)    │    │           │  │
│  │  │  └──────────────┘  └──────────────┘    │           │  │
│  │  └──────────────────────────────────────────┘           │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

## Resource Requirements

### Minimum (CronJobs)
- **Nodes**: 2-3 nodes
- **CPU**: 4 cores total
- **Memory**: 8 GB total
- **Storage**: 20 GB

### Recommended (Airflow)
- **Nodes**: 3-5 nodes
- **CPU**: 8 cores total
- **Memory**: 16 GB total
- **Storage**: 30 GB

### Per-Component Resources

| Component | Requests | Limits |
|-----------|----------|--------|
| Trading API | 250m CPU, 512Mi RAM | 1 CPU, 2Gi RAM |
| Redis | 100m CPU, 256Mi RAM | 500m CPU, 512Mi RAM |
| Airflow Webserver | 250m CPU, 512Mi RAM | 500m CPU, 1Gi RAM |
| Airflow Scheduler | 250m CPU, 512Mi RAM | 1 CPU, 2Gi RAM |
| Airflow Worker | 500m CPU, 1Gi RAM | 2 CPU, 4Gi RAM |
| PostgreSQL | 100m CPU, 256Mi RAM | 500m CPU, 1Gi RAM |

## Important Notes

1. **Update Secrets**: Edit [secrets.yaml](secrets.yaml) with actual values before deploying
2. **Storage Class**: Manifests use `trading-storage` - create or update to match your cluster
3. **Image Registry**: Replace `your-registry.com/trading-api:latest` with your Docker image
4. **Domain Name**: Update `trading-api.yourdomain.com` in [ingress.yaml](ingress.yaml)
5. **SSL/TLS**: Configure cert-manager for automatic SSL certificates
6. **Fernet Key**: Generate Airflow fernet key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

## Monitoring & Logs

```bash
# Check pod status
kubectl get pods -n trading-system

# View API logs
kubectl logs -f deployment/trading-api -n trading-system

# View Airflow scheduler logs
kubectl logs -f deployment/airflow-scheduler -n trading-system

# View CronJob history
kubectl get jobs -n trading-system --sort-by=.status.startTime

# Access Airflow UI
kubectl port-forward svc/airflow-webserver 8080:8080 -n trading-system
# Then open: http://localhost:8080
```

## Verification

```bash
# Port forward API
kubectl port-forward svc/trading-api-service 5000:5000 -n trading-system

# Test health endpoint
curl http://localhost:5000/api/health

# Test prediction (requires API key)
curl -X POST http://localhost:5000/api/predict/trend-break \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"ticker": "AAPL", "start_date": "2023-01-01", "end_date": "2024-01-15"}'
```

## Cleanup

```bash
# Delete entire namespace (WARNING: Deletes everything!)
kubectl delete namespace trading-system

# Or delete specific components
kubectl delete -f cronjobs/
kubectl delete -f airflow/
kubectl delete -f api-deployment.yaml
```

## Support

For detailed deployment instructions, see [DEPLOYMENT_INSTRUCTIONS.md](DEPLOYMENT_INSTRUCTIONS.md)
