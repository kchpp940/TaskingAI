# ============================================================
# TaskingAI Plugin Dockerfile
# Build context: project root (docker build -f plugin/Dockerfile .)
# ============================================================

# Use a specific version for reproducibility
FROM python:3.10.12-slim

# Set environment variables
ENV PYTHONPATH=/code/ \
    PYTHONIOENCODING=utf-8 \
    API_RUN_ENV=docker \
    TERM=xterm-256color \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /code

# Install system dependencies and fonts
RUN apt-get update && apt-get install -y \
    fonts-noto \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# Step 1: Install shared packages (cached layer)
# contracts: taskingai-contracts (shared schema validation)
# common: taskingai-common (tkhelper utilities - reserved for future use)
# ============================================================
COPY contracts/python /code/contracts/python
COPY common/python /code/common/python
RUN pip3 install --no-cache-dir /code/contracts/python \
 && pip3 install --no-cache-dir /code/common/python

# ============================================================
# Step 2: Install service dependencies (cached layer)
# ============================================================
COPY plugin/requirements.txt /code/requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

# ============================================================
# Step 3: Copy application code
# ============================================================
COPY plugin/app /code/app
COPY plugin/bundles /code/bundles
COPY plugin/bundle_dependency /code/bundle_dependency
COPY plugin/config.py /code/config.py

# Expose port 8000
EXPOSE 8000

# Command to run the application using gunicorn
CMD gunicorn --bind 0.0.0.0:8000 \
         --preload \
         --access-logfile - \
         --error-logfile - \
         --worker-connections 200 \
         -k uvicorn.workers.UvicornWorker \
         app.fastapi_app:app
