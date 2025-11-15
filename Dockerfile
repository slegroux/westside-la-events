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
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install Google Cloud SDK for gsutil (needed to download database from Cloud Storage)
RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list \
    && curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key --keyring /usr/share/keyrings/cloud.google.gpg add - \
    && apt-get update && apt-get install -y google-cloud-cli \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with optimizations
RUN pip install --no-cache-dir -r requirements.txt

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

# Copy entrypoint script and make it executable
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Run the application via entrypoint script
CMD ["/app/entrypoint.sh"]
