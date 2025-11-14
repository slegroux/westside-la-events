#!/bin/bash
# Sync local database to Google Cloud Storage
# Usage: ./scripts/sync_db_to_cloud.sh [--run-scrapers] [--skip-backup] [--force]
#
# This script:
# 1. (Optional) Downloads current production DB and backs it up
# 2. (Optional) Runs scrapers to update the local DB
# 3. Uploads the updated DB to Cloud Storage
# 4. Optionally restarts the Cloud Run service to pick up changes
#
# Options:
#   --run-scrapers   Run scrapers before uploading
#   --skip-backup    Don't backup the production DB before overwriting
#   --force          Skip confirmation prompts
#   --dry-run        Show what would be done without doing it

set -e  # Exit on error

# Configuration
PROJECT_ID="westside-events-406046958598"
SERVICE_NAME="westside-events"
REGION="us-west1"
BUCKET_NAME="westside-la-events-data"
LOCAL_DB="./data/events.db"
LOCAL_ANALYTICS="./data/analytics.db"
LOCAL_GEOCODE="./data/geocode_cache.json"

# Parse command line arguments
RUN_SCRAPERS=false
SKIP_BACKUP=false
FORCE=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --run-scrapers)
            RUN_SCRAPERS=true
            shift
            ;;
        --skip-backup)
            SKIP_BACKUP=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            echo "Usage: ./scripts/sync_db_to_cloud.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --run-scrapers   Run scrapers before uploading"
            echo "  --skip-backup    Don't backup the production DB before overwriting"
            echo "  --force          Skip confirmation prompts"
            echo "  --dry-run        Show what would be done without doing it"
            echo "  -h, --help       Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run with --help for usage information"
            exit 1
            ;;
    esac
done

echo "🔄 Syncing Database to Google Cloud Storage"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if gcloud is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "❌ Error: Not authenticated with gcloud"
    echo "Run: gcloud auth login"
    exit 1
fi

# Set the project
gcloud config set project ${PROJECT_ID} --quiet

# Check if local database exists
if [ ! -f "${LOCAL_DB}" ]; then
    echo "❌ Error: Local database not found at ${LOCAL_DB}"
    exit 1
fi

# Show current database stats
if [ -f "${LOCAL_DB}" ]; then
    EVENT_COUNT=$(sqlite3 "${LOCAL_DB}" "SELECT COUNT(*) FROM events;" 2>/dev/null || echo "0")
    echo "📊 Local database stats:"
    echo "   Events: ${EVENT_COUNT}"
    echo "   Size: $(du -h "${LOCAL_DB}" | cut -f1)"
    echo ""
fi

# Backup production database if not skipped
if [ "$SKIP_BACKUP" = false ]; then
    echo "💾 Backing up production database..."
    BACKUP_DIR="./data/backup"
    mkdir -p "${BACKUP_DIR}"
    BACKUP_TIMESTAMP=$(date +%Y%m%d_%H%M%S)

    if [ "$DRY_RUN" = false ]; then
        gsutil cp "gs://${BUCKET_NAME}/events.db" "${BACKUP_DIR}/events_prod_${BACKUP_TIMESTAMP}.db" 2>/dev/null || {
            echo "⚠️  Warning: Could not backup production database (it may not exist yet)"
        }
    else
        echo "   [DRY RUN] Would download: gs://${BUCKET_NAME}/events.db -> ${BACKUP_DIR}/events_prod_${BACKUP_TIMESTAMP}.db"
    fi
    echo ""
fi

# Run scrapers if requested
if [ "$RUN_SCRAPERS" = true ]; then
    echo "🕷️  Running scrapers to update local database..."
    echo ""

    if [ "$DRY_RUN" = false ]; then
        # Check if micromamba is available
        if command -v micromamba &> /dev/null; then
            # Run scrapers with clean environment
            bash -c 'unset PYTHONPATH; micromamba run -n la python run_scrapers.py' || {
                echo "❌ Error: Scrapers failed"
                exit 1
            }
        else
            echo "❌ Error: micromamba not found"
            exit 1
        fi
    else
        echo "   [DRY RUN] Would run: micromamba run -n la python run_scrapers.py"
    fi

    # Update event count after scraping
    if [ -f "${LOCAL_DB}" ] && [ "$DRY_RUN" = false ]; then
        EVENT_COUNT=$(sqlite3 "${LOCAL_DB}" "SELECT COUNT(*) FROM events;" 2>/dev/null || echo "0")
        echo ""
        echo "📊 Updated database stats:"
        echo "   Events: ${EVENT_COUNT}"
        echo "   Size: $(du -h "${LOCAL_DB}" | cut -f1)"
        echo ""
    fi
fi

# Confirmation prompt (unless forced or dry run)
if [ "$FORCE" = false ] && [ "$DRY_RUN" = false ]; then
    echo "⚠️  This will overwrite the production database in Cloud Storage."
    read -p "Continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
    echo ""
fi

# Upload database to Cloud Storage
echo "☁️  Uploading database to Cloud Storage..."

if [ "$DRY_RUN" = false ]; then
    # Upload events database
    gsutil cp "${LOCAL_DB}" "gs://${BUCKET_NAME}/events.db"
    echo "   ✓ Uploaded events.db"

    # Upload analytics database if it exists
    if [ -f "${LOCAL_ANALYTICS}" ]; then
        gsutil cp "${LOCAL_ANALYTICS}" "gs://${BUCKET_NAME}/analytics.db"
        echo "   ✓ Uploaded analytics.db"
    fi

    # Upload geocode cache if it exists
    if [ -f "${LOCAL_GEOCODE}" ]; then
        gsutil cp "${LOCAL_GEOCODE}" "gs://${BUCKET_NAME}/geocode_cache.json"
        echo "   ✓ Uploaded geocode_cache.json"
    fi
else
    echo "   [DRY RUN] Would upload:"
    echo "      ${LOCAL_DB} -> gs://${BUCKET_NAME}/events.db"
    [ -f "${LOCAL_ANALYTICS}" ] && echo "      ${LOCAL_ANALYTICS} -> gs://${BUCKET_NAME}/analytics.db"
    [ -f "${LOCAL_GEOCODE}" ] && echo "      ${LOCAL_GEOCODE} -> gs://${BUCKET_NAME}/geocode_cache.json"
fi

echo ""

# Verify uploaded files
if [ "$DRY_RUN" = false ]; then
    echo "🔍 Verifying uploaded files..."
    gsutil ls -lh "gs://${BUCKET_NAME}/" | grep -E "(events\.db|analytics\.db|geocode_cache\.json)"
    echo ""
fi

# Display completion message
echo "✅ Database sync complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$DRY_RUN" = false ]; then
    echo "🌐 Cloud Storage: gs://${BUCKET_NAME}/"
    echo "📊 Events in database: ${EVENT_COUNT}"
    echo ""
    echo "The Cloud Run service will automatically use the updated database"
    echo "on the next request (cold start). To force an immediate restart:"
    echo ""
    echo "  gcloud run services update ${SERVICE_NAME} --region ${REGION}"
    echo ""
else
    echo "[DRY RUN] No changes were made"
    echo ""
fi

# Display backup location if created
if [ "$SKIP_BACKUP" = false ] && [ "$DRY_RUN" = false ]; then
    echo "💾 Production backup saved to:"
    echo "   ${BACKUP_DIR}/events_prod_${BACKUP_TIMESTAMP}.db"
    echo ""
fi
