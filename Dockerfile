# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Playwright and other tools
# Combine into single layer and use --no-install-recommends to reduce size
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with optimizations
# Use pip cache mount for faster rebuilds (if BuildKit is enabled)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (this is the slowest step - ~500MB)
# Cache this layer separately so it only rebuilds if requirements change
RUN playwright install --with-deps chromium && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

# Copy application code (this changes most frequently, so it's last)
COPY . .

# Create data directory for SQLite
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

# Expose port (Cloud Run will set $PORT environment variable)
EXPOSE 8080

# Run the application
CMD uvicorn src.web.app:app --host 0.0.0.0 --port ${PORT:-8080}
