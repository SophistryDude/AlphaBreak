# Trading Prediction API Dockerfile
# ==================================
# Simplified single-stage build for local development
#
# BUILD FROM PROJECT ROOT:
#   docker build -f flask_app/Dockerfile -t trading-api:latest .

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    FLASK_ENV=production \
    PORT=5000

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

# Copy and install Python dependencies
COPY flask_app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy src modules (core prediction logic)
COPY src/ /app/src/

# Copy flask_app (API layer)
COPY flask_app/app/ /app/flask_app/app/
COPY flask_app/wsgi.py /app/flask_app/
COPY flask_app/gunicorn_config.py /app/flask_app/

# Create directories and set permissions
RUN mkdir -p /app/logs /app/models \
    && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

# Set working directory for flask_app
WORKDIR /app/flask_app

# Run with Gunicorn
CMD ["gunicorn", "-c", "gunicorn_config.py", "wsgi:app"]
