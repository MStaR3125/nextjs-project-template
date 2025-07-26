# Backend Dockerfile for FastAPI Application
# This creates a containerized Python environment for the scraping API

# Use Python 3.9 slim image for smaller size and security
FROM python:3.9-slim

# Set metadata labels for the image
LABEL maintainer="Autonomous Scraper Team"
LABEL description="FastAPI backend for web scraping system"
LABEL version="1.0.0"

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE=1  # Prevents Python from writing .pyc files
ENV PYTHONUNBUFFERED=1         # Ensures Python output is sent straight to terminal
ENV PYTHONPATH=/app            # Set Python path to app directory

# Create a non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory inside the container
WORKDIR /app

# Install system dependencies
# These are required for some Python packages and MongoDB connectivity
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements file first for better Docker layer caching
# This allows pip install to be cached if dependencies haven't changed
COPY requirements.txt .

# Install Python dependencies
# --no-cache-dir reduces image size by not storing pip cache
# --upgrade ensures we get the latest versions
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code to container
COPY . .

# Change ownership of the app directory to the non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user for security
USER appuser

# Create directory for logs (if needed)
RUN mkdir -p /app/logs

# Expose port 8000 for the FastAPI application
EXPOSE 8000

# Health check to ensure the application is running properly
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Command to run the FastAPI application
# --host 0.0.0.0 allows connections from outside the container
# --port 8000 specifies the port to listen on
# --workers 1 sets the number of worker processes (can be increased for production)
# --log-level info provides detailed logging
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--log-level", "info"]
