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
worker_class = 'sync'  # Use 'eventlet' when flask-socketio is installed
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

# Logging — JSON structured output for log aggregation
accesslog = '-'  # Log to stdout
errorlog = '-'   # Log to stderr
loglevel = os.environ.get('GUNICORN_LOG_LEVEL', 'info')

# JSON access log format consumed by log collectors (FluentBit, Loki, etc.)
access_log_format = (
    '{"timestamp":"%(t)s","remote_addr":"%(h)s","method":"%(m)s",'
    '"path":"%(U)s","query":"%(q)s","protocol":"%(H)s",'
    '"status":%(s)s,"response_bytes":%(B)s,'
    '"referer":"%(f)s","user_agent":"%(a)s","duration_us":%(D)s}'
)

logconfig_dict = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'fmt': '%(asctime)s %(levelname)s %(name)s %(message)s',
            'rename_fields': {
                'asctime': 'timestamp',
                'levelname': 'level',
            },
            'datefmt': '%Y-%m-%dT%H:%M:%S%z',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
            'stream': 'ext://sys.stdout',
        },
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console'],
    },
    'loggers': {
        'gunicorn.error': {
            'level': 'INFO',
            'handlers': ['console'],
            'propagate': False,
        },
        'gunicorn.access': {
            'level': 'INFO',
            'handlers': ['console'],
            'propagate': False,
        },
    },
}

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
