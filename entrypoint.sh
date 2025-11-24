#!/bin/bash

echo "🚀 Starting Westside Events application..."

# By default, skip database download and use bundled version (faster cold starts)
# Set SKIP_DB_DOWNLOAD=false to force download from Cloud Storage
if [ "$SKIP_DB_DOWNLOAD" = "true" ]; then
    echo "⚡ Using bundled database (fast startup mode)"
    echo "   Database is baked into the Docker image for instant cold starts"
else
    # Download database from Cloud Storage if it exists
    BUCKET="gs://westside-la-events-data"

    echo "📥 Downloading database from Cloud Storage..."
    # Try to download events.db but only if it's larger than bundled version
    if gsutil -q stat "${BUCKET}/events.db" 2>/dev/null; then
        # Get size of Cloud Storage database
        cloud_size=$(gsutil ls -l "${BUCKET}/events.db" | awk '{print $1}')

        # Get size of bundled database (if it exists)
        if [ -f "/app/data/events.db" ]; then
            bundled_size=$(stat -c%s "/app/data/events.db" 2>/dev/null || stat -f%z "/app/data/events.db" 2>/dev/null)
        else
            bundled_size=0
        fi

        # Smart download logic:
        # 1. If no bundled database exists, always download from Cloud Storage
        # 2. If Cloud Storage database is larger, download it (more events)
        # 3. Otherwise, keep bundled version
        if [ "$bundled_size" -eq 0 ]; then
            # No bundled database, download from Cloud Storage (even if small)
            echo "📦 No bundled database found, downloading from Cloud Storage..."
            gsutil cp "${BUCKET}/events.db" /app/data/events.db && echo "✓ Downloaded events.db (${cloud_size} bytes)"
        elif [ "$cloud_size" -gt "$bundled_size" ]; then
            # Cloud Storage has more events, download it
            echo "📦 Cloud Storage database is larger (${cloud_size} > ${bundled_size}), updating..."
            gsutil cp "${BUCKET}/events.db" /app/data/events.db && echo "✓ Downloaded events.db (${cloud_size} bytes)"
        else
            # Bundled version is larger or equal, keep it
            echo "✅ Using bundled database (${bundled_size} bytes >= ${cloud_size} bytes)"
        fi
    else
        echo "⚠️  No events.db found in Cloud Storage, using bundled database"
    fi

    # Try to download analytics.db (don't exit on failure)
    if gsutil -q stat "${BUCKET}/analytics.db" 2>/dev/null; then
        gsutil cp "${BUCKET}/analytics.db" /app/data/analytics.db && echo "✓ Downloaded analytics.db"
    else
        echo "⚠️  No analytics.db found in Cloud Storage, starting with empty analytics"
    fi

    # Try to download geocode_cache.json (don't exit on failure)
    if gsutil -q stat "${BUCKET}/geocode_cache.json" 2>/dev/null; then
        gsutil cp "${BUCKET}/geocode_cache.json" /app/data/geocode_cache.json && echo "✓ Downloaded geocode_cache.json"
    else
        echo "⚠️  No geocode_cache.json found in Cloud Storage"
    fi

    echo "✅ Database sync complete"
fi

echo ""

# Start the application
exec uvicorn src.web.app:app --host 0.0.0.0 --port ${PORT:-8080}
