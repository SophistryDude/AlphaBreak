# Kubernetes PostgreSQL Migration Guide

This guide covers migrating from native PostgreSQL on EC2 to a fully containerized Kubernetes deployment.

**Prerequisites:** EC2 instance with at least 2GB RAM (t3.small) or 4GB RAM (t3.medium recommended)

---

## Table of Contents

1. [Upgrade EC2 Instance](#1-upgrade-ec2-instance)
2. [Backup Current Database](#2-backup-current-database)
3. [Stop Native PostgreSQL](#3-stop-native-postgresql)
4. [Create Persistent Storage](#4-create-persistent-storage)
5. [Deploy PostgreSQL in Kubernetes](#5-deploy-postgresql-in-kubernetes)
6. [Restore Database](#6-restore-database)
7. [Deploy Trading API](#7-deploy-trading-api)
8. [Verify Deployment](#8-verify-deployment)

---

## 1. Upgrade EC2 Instance

### Option A: Resize existing instance

```bash
# Stop the instance (from AWS Console or CLI)
aws ec2 stop-instances --instance-ids i-xxxxxxxxx

# Change instance type
aws ec2 modify-instance-attribute \
    --instance-id i-xxxxxxxxx \
    --instance-type "{\"Value\": \"t3.small\"}"

# Start the instance
aws ec2 start-instances --instance-ids i-xxxxxxxxx
```

**Note:** Elastic IP will remain attached. Instance will have a new private IP.

### Option B: Launch new instance

1. Launch t3.small or t3.medium with Ubuntu 22.04
2. Allocate and associate a new Elastic IP
3. Follow the [EC2 Kubernetes Guide](./EC2_KUBERNETES_GUIDE.md) to install k0s

---

## 2. Backup Current Database

SSH to your EC2 instance:

```bash
ssh -i ~/.ssh/trading-db-key.pem ubuntu@YOUR_EC2_IP
```

Create a backup:

```bash
# Custom format (smaller, faster restore)
sudo -u postgres pg_dump -Fc trading_data > ~/trading_data_backup.dump

# Verify backup size
ls -lh ~/trading_data_backup.dump
```

---

## 3. Stop Native PostgreSQL

```bash
# Stop PostgreSQL service
sudo systemctl stop postgresql

# Disable auto-start (we'll use K8s instead)
sudo systemctl disable postgresql

# Free up memory
sudo systemctl daemon-reload

# Verify it's stopped
sudo systemctl status postgresql
```

---

## 4. Create Persistent Storage

Create directories for persistent data:

```bash
# Create data directories
sudo mkdir -p /data/postgresql
sudo mkdir -p /data/models
sudo mkdir -p /data/logs

# Set permissions
sudo chown -R 999:999 /data/postgresql  # PostgreSQL container user
sudo chmod 700 /data/postgresql
```

Create the PersistentVolume manifests:

```yaml
# Save as /home/ubuntu/k8s/persistent-volumes.yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: postgres-pv
spec:
  capacity:
    storage: 20Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: local-storage
  local:
    path: /data/postgresql
  nodeAffinity:
    required:
      nodeSelectorTerms:
      - matchExpressions:
        - key: kubernetes.io/hostname
          operator: In
          values:
          - ip-172-31-22-21  # Your node name
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-pvc
  namespace: trading-system
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: local-storage
  resources:
    requests:
      storage: 20Gi
```

Apply:

```bash
kubectl apply -f /home/ubuntu/k8s/persistent-volumes.yaml
```

---

## 5. Deploy PostgreSQL in Kubernetes

Create the PostgreSQL deployment:

```yaml
# Save as /home/ubuntu/k8s/postgres-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres-timescaledb
  namespace: trading-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres-timescaledb
  template:
    metadata:
      labels:
        app: postgres-timescaledb
    spec:
      containers:
      - name: postgres
        image: timescale/timescaledb:latest-pg15
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_DB
          value: "trading_data"
        - name: POSTGRES_USER
          value: "trading"
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: trading-secrets
              key: db-password
        - name: PGDATA
          value: /var/lib/postgresql/data/pgdata
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        volumeMounts:
        - name: postgres-data
          mountPath: /var/lib/postgresql/data
        livenessProbe:
          exec:
            command: ["pg_isready", "-U", "trading", "-d", "trading_data"]
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          exec:
            command: ["pg_isready", "-U", "trading", "-d", "trading_data"]
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: postgres-data
        persistentVolumeClaim:
          claimName: postgres-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: postgres-service
  namespace: trading-system
spec:
  selector:
    app: postgres-timescaledb
  ports:
  - port: 5432
    targetPort: 5432
  type: ClusterIP
```

Create the secret:

```bash
kubectl create secret generic trading-secrets \
  --namespace trading-system \
  --from-literal=db-password='YOUR_SECURE_PASSWORD'
```

Deploy:

```bash
kubectl apply -f /home/ubuntu/k8s/postgres-deployment.yaml

# Wait for pod to be ready
kubectl get pods -n trading-system -w
```

---

## 6. Restore Database

Copy backup to the PostgreSQL pod:

```bash
# Get pod name
POD=$(kubectl get pods -n trading-system -l app=postgres-timescaledb -o jsonpath='{.items[0].metadata.name}')

# Copy backup file to pod
kubectl cp ~/trading_data_backup.dump trading-system/$POD:/tmp/

# Restore database
kubectl exec -n trading-system $POD -- pg_restore \
  -U trading \
  -d trading_data \
  -v \
  /tmp/trading_data_backup.dump

# Verify restore
kubectl exec -n trading-system $POD -- psql -U trading -d trading_data \
  -c "SELECT COUNT(*) FROM stock_prices;"
```

---

## 7. Deploy Trading API

Create the API deployment:

```yaml
# Save as /home/ubuntu/k8s/trading-api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trading-api
  namespace: trading-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: trading-api
  template:
    metadata:
      labels:
        app: trading-api
    spec:
      containers:
      - name: trading-api
        image: YOUR_DOCKERHUB_USER/trading-api:latest
        ports:
        - containerPort: 5000
        env:
        - name: FLASK_ENV
          value: "production"
        - name: TIMESERIES_DB_HOST
          value: "postgres-service"
        - name: TIMESERIES_DB_PORT
          value: "5432"
        - name: TIMESERIES_DB_NAME
          value: "trading_data"
        - name: TIMESERIES_DB_USER
          value: "trading"
        - name: TIMESERIES_DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: trading-secrets
              key: db-password
        - name: TIMESERIES_DB_SSLMODE
          value: "prefer"
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /api/health
            port: 5000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/health
            port: 5000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: trading-api-service
  namespace: trading-system
spec:
  type: NodePort
  selector:
    app: trading-api
  ports:
  - port: 5000
    targetPort: 5000
    nodePort: 30500
```

### Build and Push Docker Image

On your local machine:

```bash
cd flask_app

# Build image
docker build -t YOUR_DOCKERHUB_USER/trading-api:latest .

# Push to Docker Hub
docker login
docker push YOUR_DOCKERHUB_USER/trading-api:latest
```

Deploy:

```bash
kubectl apply -f /home/ubuntu/k8s/trading-api-deployment.yaml
```

---

## 8. Verify Deployment

### Check all pods are running

```bash
kubectl get pods -n trading-system
```

Expected output:
```
NAME                                  READY   STATUS    RESTARTS   AGE
postgres-timescaledb-xxx              1/1     Running   0          5m
trading-api-xxx                       1/1     Running   0          2m
redis-xxx                             1/1     Running   0          5m
```

### Test API

```bash
# From EC2
curl http://localhost:30500/api/health

# From local machine
curl http://YOUR_EC2_IP:30500/api/health
```

### Check database connection

```bash
kubectl exec -n trading-system deployment/trading-api -- \
  python -c "from app.utils.database import db_manager; print(db_manager.execute_query('SELECT 1'))"
```

---

## Resource Summary

| Component | Memory Request | Memory Limit | CPU Request | CPU Limit |
|-----------|---------------|--------------|-------------|-----------|
| PostgreSQL | 512Mi | 1Gi | 250m | 1000m |
| Trading API | 256Mi | 512Mi | 100m | 500m |
| Redis | 64Mi | 128Mi | 50m | 200m |
| k0s overhead | ~300Mi | - | - | - |
| **Total** | **~1.2Gi** | **~2Gi** | - | - |

**Recommended instance:** t3.small (2GB) minimum, t3.medium (4GB) for comfort

---

## Rollback Plan

If something goes wrong:

```bash
# Delete K8s deployments
kubectl delete namespace trading-system

# Re-enable native PostgreSQL
sudo systemctl enable postgresql
sudo systemctl start postgresql

# Verify
sudo -u postgres psql -c "SELECT COUNT(*) FROM stock_prices;"
```

---

## Security Considerations

1. **Secrets management**: Consider using AWS Secrets Manager or HashiCorp Vault instead of K8s secrets
2. **Network policies**: Restrict pod-to-pod communication
3. **Pod security**: Run containers as non-root
4. **Backup schedule**: Set up automated pg_dump via CronJob

---

## Next Steps After Migration

1. Set up automated backups with K8s CronJob
2. Configure horizontal pod autoscaling for the API
3. Add Prometheus + Grafana for monitoring
4. Set up cert-manager for TLS
5. Configure Ingress for external access
