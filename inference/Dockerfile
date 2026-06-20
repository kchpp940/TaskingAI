# ============================================================
# TaskingAI Inference Dockerfile
# Build context: project root (docker build -f inference/Dockerfile .)
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
COPY inference/requirements.txt /code/requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

# ============================================================
# Step 3: Copy application code
# ============================================================
COPY inference/app /code/app
COPY inference/providers /code/providers
COPY inference/provider_dependency /code/provider_dependency
COPY inference/config.py /code/config.py
COPY inference/scripts /code/scripts

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
