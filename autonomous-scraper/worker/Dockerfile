# Worker Dockerfile for Python Scraping Agent
# This creates a containerized environment with Playwright for web scraping

# Use Microsoft's Playwright image which includes browsers and dependencies
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Set metadata labels for the image
LABEL maintainer="Autonomous Scraper Team"
LABEL description="Python worker for web scraping with Playwright"
LABEL version="1.0.0"

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1  # Prevents Python from writing .pyc files
ENV PYTHONUNBUFFERED=1         # Ensures Python output is sent straight to terminal
ENV PYTHONPATH=/app            # Set Python path to app directory

# Set Playwright environment variables
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

# Create a non-root user for security
RUN groupadd -r worker && useradd -r -g worker worker

# Set working directory inside the container
WORKDIR /app

# Install additional system dependencies if needed
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements file first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
# --no-cache-dir reduces image size by not storing pip cache
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (they should already be installed in the base image)
# This is a safety measure in case they're not present
RUN python -m playwright install --with-deps chromium firefox webkit

# Copy application code to container
COPY . .

# Create directories for logs and temporary files
RUN mkdir -p /app/logs /app/temp

# Change ownership of the app directory to the worker user
RUN chown -R worker:worker /app

# Switch to non-root user for security
USER worker

# Health check to ensure the worker can connect to required services
HEALTHCHECK --interval=60s --timeout=30s --start-period=10s --retries=3 \
    CMD python -c "import asyncio; import motor.motor_asyncio; print('Worker health check passed')" || exit 1

# Set the command to run the worker
# The worker will continuously poll for jobs and process them
CMD ["python", "worker.py"]
