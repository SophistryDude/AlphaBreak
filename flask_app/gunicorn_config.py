"""
Gunicorn Configuration
=======================
Production server configuration for Gunicorn WSGI server.

Usage:
    gunicorn -c gunicorn_config.py wsgi:app
"""

import os
import multiprocessing

# Server Socket
bind = os.environ.get('GUNICORN_BIND', '0.0.0.0:5000')
backlog = 2048

# Worker Processes
# Use 2 workers for container deployment to avoid OOM
workers = int(os.environ.get('GUNICORN_WORKERS', 2))
worker_class = 'sync'  # Use 'gevent' or 'eventlet' for async
worker_connections = 1000
max_requests = 1000  # Restart workers after this many requests (prevents memory leaks)
max_requests_jitter = 50  # Add randomness to max_requests

# Timeouts
timeout = 120  # Worker timeout in seconds (increase for long-running predictions)
graceful_timeout = 30  # Graceful shutdown timeout
keepalive = 5  # Keep-alive connections

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Server Mechanics
daemon = False  # Run in foreground (for Docker)
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Logging
accesslog = '-'  # Log to stdout
errorlog = '-'   # Log to stderr
loglevel = os.environ.get('GUNICORN_LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process Naming
proc_name = 'trading-prediction-api'

# Server Hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    print("Starting Trading Prediction API server...")


def on_reload(server):
    """Called when server receives SIGHUP signal."""
    print("Reloading Trading Prediction API server...")


def worker_int(worker):
    """Called when a worker receives SIGINT or SIGQUIT."""
    print(f"Worker {worker.pid} received INT or QUIT signal")


def worker_abort(worker):
    """Called when a worker receives SIGABRT signal."""
    print(f"Worker {worker.pid} received ABORT signal")


def pre_fork(server, worker):
    """Called just before a worker is forked."""
    pass


def post_fork(server, worker):
    """Called just after a worker has been forked."""
    print(f"Worker spawned (pid: {worker.pid})")


def post_worker_init(worker):
    """Called just after a worker has initialized the application."""
    pass


def worker_exit(server, worker):
    """Called just after a worker has been exited."""
    print(f"Worker exited (pid: {worker.pid})")


def nworkers_changed(server, new_value, old_value):
    """Called when number of workers has been changed."""
    print(f"Number of workers changed from {old_value} to {new_value}")


def on_exit(server):
    """Called just before exiting Gunicorn."""
    print("Shutting down Trading Prediction API server...")


# Preloading
preload_app = True  # Load app before forking workers (saves memory)


# SSL Configuration (uncomment for HTTPS)
# keyfile = '/path/to/keyfile'
# certfile = '/path/to/certfile'
# ssl_version = 'TLSv1_2'
# cert_reqs = 0  # ssl.CERT_NONE
# ca_certs = None
# suppress_ragged_eofs = True
# do_handshake_on_connect = False
