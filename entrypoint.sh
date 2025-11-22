#!/bin/bash

echo "🚀 Starting Westside Events application..."

# Download database from Cloud Storage if it exists
BUCKET="gs://westside-la-events-data"

echo "📥 Downloading database from Cloud Storage..."
# Try to download events.db (don't exit on failure)
if gsutil -q stat "${BUCKET}/events.db" 2>/dev/null; then
    gsutil cp "${BUCKET}/events.db" /app/data/events.db && echo "✓ Downloaded events.db"
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
echo ""

# Start the application
exec uvicorn src.web.app:app --host 0.0.0.0 --port ${PORT:-8080}
