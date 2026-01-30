# AlphaBreak Kubernetes Deployment Instructions

Complete step-by-step guide to deploy AlphaBreak on Kubernetes with Airflow scheduling.

## Prerequisites

- Kubernetes cluster (EKS, GKE, AKS, or local with minikube)
- kubectl configured
- Docker installed (for building images)
- Helm (optional, for Airflow)

## Quick Start

### 1. Build and Push Docker Image

```bash
# Build image
cd flask_app
docker build -t trading-api:latest .

# Tag for your registry
docker tag trading-api:latest your-registry.com/trading-api:latest

# Push to registry
docker push your-registry.com/trading-api:latest
```

### 2. Deploy to Kubernetes

```bash
# Create namespace
kubectl apply -f kubernetes/namespace.yaml

# Create secrets (IMPORTANT: Update secrets.yaml first!)
kubectl apply -f kubernetes/secrets.yaml

# Create configmap
kubectl apply -f kubernetes/configmap.yaml

# Deploy Redis
kubectl apply -f kubernetes/redis-deployment.yaml

# Deploy API
kubectl apply -f kubernetes/api-deployment.yaml
kubectl apply -f kubernetes/api-service.yaml

# Deploy Ingress
kubectl apply -f kubernetes/ingress.yaml

# Deploy CronJobs
kubectl apply -f kubernetes/cronjobs/indicator-analysis-cronjob.yaml
kubectl apply -f kubernetes/cronjobs/model-retraining-cronjob.yaml

# OR Deploy Airflow (recommended)
kubectl apply -f kubernetes/airflow/
```

### 3. Verify Deployment

```bash
# Check pods
kubectl get pods -n trading-system

# Check services
kubectl get svc -n trading-system

# Check logs
kubectl logs -f deployment/trading-api -n trading-system

# Port forward to access API locally
kubectl port-forward svc/trading-api-service 5000:5000 -n trading-system
```

### 4. Test API

```bash
# Health check
curl http://localhost:5000/api/health

# Predict trend break
curl -X POST http://localhost:5000/api/predict/trend-break \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"ticker": "AAPL", "start_date": "2023-01-01", "end_date": "2024-01-15"}'
```

## Deployment Options

### Option 1: CronJobs (Simpler)

**Pros:**
- Built into Kubernetes
- No additional services
- Simple configuration

**Cons:**
- Limited monitoring
- No dependency management
- Basic retry logic

**Deploy:**
```bash
kubectl apply -f kubernetes/cronjobs/
```

**Monitor:**
```bash
# List cronjobs
kubectl get cronjobs -n trading-system

# View job history
kubectl get jobs -n trading-system

# Check logs
kubectl logs job/indicator-analysis-job-<timestamp> -n trading-system
```

### Option 2: Apache Airflow (Recommended for Production)

**Pros:**
- Advanced DAG-based scheduling
- Comprehensive monitoring
- Built-in retry & alerting
- Web UI for management

**Cons:**
- More complex setup
- Additional resource overhead

**Deploy with Helm:**
```bash
# Add Airflow Helm repo
helm repo add apache-airflow https://airflow.apache.org
helm repo update

# Install Airflow
helm install airflow apache-airflow/airflow \
  --namespace trading-system \
  --set executor=CeleryExecutor \
  --set redis.enabled=true \
  --set postgresql.enabled=true \
  -f kubernetes/airflow/values.yaml
```

**Access Airflow UI:**
```bash
# Port forward
kubectl port-forward svc/airflow-webserver 8080:8080 -n trading-system

# Open browser: http://localhost:8080
# Username: admin
# Password: (from secrets)
```

## Scheduled Tasks

### CronJob Schedules

| Job | Schedule | Purpose |
|-----|----------|---------|
| indicator-analysis | Daily 2 AM | Analyze indicator accuracy |
| model-retraining | Weekly Sunday 3 AM | Retrain all models |
| backtest | Monthly 1st, 4 AM | Run backtests |

### Airflow DAGs

| DAG | Schedule | Tasks |
|-----|----------|-------|
| model_retraining_pipeline | Weekly Sunday 3 AM | 7-step retraining workflow |
| indicator_analysis_dag | Daily 2 AM | Daily indicator analysis |
| backtest_dag | Monthly 1st | Monthly backtesting |

## Monitoring

### Check API Health

```bash
kubectl get pods -n trading-system -l app=trading-api
kubectl logs -f deployment/trading-api -n trading-system
```

### Check CronJobs

```bash
# List all cronjobs
kubectl get cronjobs -n trading-system

# View specific cronjob
kubectl describe cronjob indicator-analysis-job -n trading-system

# View recent jobs
kubectl get jobs -n trading-system --sort-by=.status.startTime
```

### Check Airflow

```bash
# Access Airflow UI (port forward first)
kubectl port-forward svc/airflow-webserver 8080:8080 -n trading-system

# Check Airflow scheduler
kubectl logs deployment/airflow-scheduler -n trading-system

# Check Airflow workers
kubectl logs deployment/airflow-worker -n trading-system
```

### Metrics & Alerts

```bash
# View resource usage
kubectl top pods -n trading-system

# Set up alerts (example with Prometheus)
kubectl apply -f kubernetes/monitoring/prometheus-rules.yaml
```

## Scaling

### Manual Scaling

```bash
# Scale API pods
kubectl scale deployment trading-api --replicas=5 -n trading-system

# Scale Airflow workers
kubectl scale deployment airflow-worker --replicas=3 -n trading-system
```

### Horizontal Pod Autoscaler (HPA)

```bash
# Enable HPA for API
kubectl apply -f kubernetes/api-hpa.yaml

# Check HPA status
kubectl get hpa -n trading-system
```

## Updating Models

### Manual Update

```bash
# Copy new models to pod
kubectl cp models/ trading-system/trading-api-pod:/app/models/

# Restart pods to load new models
kubectl rollout restart deployment/trading-api -n trading-system
```

### Automated Update (via CronJob/Airflow)

Models are automatically updated on schedule by:
1. CronJob: `model-retraining-job` (weekly)
2. Airflow: `model_retraining_pipeline` DAG (weekly)

## Troubleshooting

### Pods not starting

```bash
kubectl describe pod <pod-name> -n trading-system
kubectl logs <pod-name> -n trading-system
```

### API not responding

```bash
# Check service
kubectl get svc trading-api-service -n trading-system

# Check endpoints
kubectl get endpoints trading-api-service -n trading-system

# Test from within cluster
kubectl run curl --image=curlimages/curl -it --rm -- curl http://trading-api-service:5000/api/health
```

### CronJob not running

```bash
# Check cronjob
kubectl describe cronjob <cronjob-name> -n trading-system

# Manual trigger
kubectl create job --from=cronjob/<cronjob-name> manual-run -n trading-system
```

### Airflow DAG failing

```bash
# Check Airflow logs
kubectl logs deployment/airflow-scheduler -n trading-system

# Access Airflow UI to view task logs
kubectl port-forward svc/airflow-webserver 8080:8080 -n trading-system
```

## Cleanup

```bash
# Delete everything in namespace
kubectl delete namespace trading-system

# Or delete individual resources
kubectl delete -f kubernetes/
```

## Production Checklist

- [ ] Update secrets with actual values
- [ ] Configure HTTPS/TLS (Ingress)
- [ ] Set up monitoring (Prometheus/Grafana)
- [ ] Configure alerting (PagerDuty/Slack)
- [ ] Set up log aggregation (ELK/CloudWatch)
- [ ] Configure backups (persistent volumes)
- [ ] Set resource limits appropriately
- [ ] Test disaster recovery
- [ ] Document runbooks
- [ ] Set up CI/CD pipeline

## Cost Optimization

1. **Right-size pods**: Monitor resource usage and adjust requests/limits
2. **Use spot instances**: For non-critical workloads
3. **Scale down off-hours**: If not trading 24/7
4. **Optimize images**: Use multi-stage builds, Alpine base
5. **Cache aggressively**: Use Redis for frequently accessed data

## Support

For issues, check:
- Pod logs: `kubectl logs -n trading-system <pod-name>`
- Events: `kubectl get events -n trading-system`
- Airflow UI: DAG run logs
- API logs: `/app/logs/trading_api.log` in pods
