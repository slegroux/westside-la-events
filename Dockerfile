# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Playwright, gsutil, and other tools
# Combine into single layer and use --no-install-recommends to reduce size
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    curl \
    ca-certificates \
    lsb-release \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install Google Cloud SDK for gsutil (needed to download database from Cloud Storage)
# Using the official install script which is more reliable than apt
RUN curl https://sdk.cloud.google.com | bash -s -- --disable-prompts --install-dir=/opt \
    && /opt/google-cloud-sdk/bin/gcloud components install gsutil --quiet

# Add gcloud to PATH
ENV PATH="/opt/google-cloud-sdk/bin:${PATH}"

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with optimizations
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (this is the slowest step - ~500MB)
# Cache this layer separately so it only rebuilds if requirements change
# Use --with-deps chromium for minimal footprint
RUN playwright install --with-deps chromium && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean && \
    # Remove unnecessary Playwright files to reduce image size
    rm -rf /root/.cache/ms-playwright/*/firefox* /root/.cache/ms-playwright/*/webkit*

# Copy application code (this changes most frequently, so it's last)
COPY . .

# Ensure data directory exists (COPY . . creates it if data/ exists locally)
RUN mkdir -p /app/data

# Set environment variables
# IMPORTANT: Set timezone to America/Los_Angeles (PST/PDT) since events are in local LA time
# This ensures SQLite's date('now', 'localtime') returns the correct local time
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    TZ=America/Los_Angeles \
    # Reduce Python startup time
    PYTHONHASHSEED=0 \
    # Skip database download on startup (database is bundled in image)
    SKIP_DB_DOWNLOAD=true

# Expose port (Cloud Run will set $PORT environment variable)
EXPOSE 8080

# Copy entrypoint script and make it executable
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Run the application via entrypoint script
CMD ["/app/entrypoint.sh"]
