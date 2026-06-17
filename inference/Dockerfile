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

# Copy shared common package first (stable, good cache layer)
COPY ./common ./common

# Copy only the requirements.txt next to leverage Docker cache
COPY ./inference/requirements.txt ./
RUN pip3 install --no-cache-dir -e ./common \
 && pip3 install --no-cache-dir -r requirements.txt

# Copy service code to working directory
COPY ./inference/app ./app
COPY ./inference/providers ./providers
COPY ./inference/provider_dependency ./provider_dependency
COPY ./inference/config.py ./
COPY ./inference/test/utils/utils.py ./test/utils/utils.py
COPY ./inference/scripts ./scripts

# Command to run the application using gunicorn
CMD gunicorn --bind 0.0.0.0:8000 \
         --preload \
         --access-logfile - \
         --error-logfile - \
         --worker-connections 200 \
         -k uvicorn.workers.UvicornWorker \
         app.fastapi_app:app

EXPOSE 8000
