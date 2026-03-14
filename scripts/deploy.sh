#!/bin/bash
# Deploy Westside LA Events to Google Cloud Run
# Usage: ./scripts/deploy.sh [--run-tests] [--rollback] [--env-file PATH] [--no-cache]
#
# Options:
#   --run-tests     Run tests before deployment (tests are skipped by default)
#   --rollback      Rollback to previous revision
#   --env-file      Path to .env file with additional environment variables
#   --no-cache      Force a clean rebuild without using Docker layer cache
#
# IMPORTANT: Secrets are managed separately via Google Secret Manager
# The SCRAPER_TOKEN is stored securely and automatically injected at runtime.
# It persists across deployments. To rotate the token:
#   1. Update the secret: echo -n "new-token" | gcloud secrets versions add scraper-token --data-file=-
#   2. Redeploy (this script) - no additional steps needed

set -e  # Exit on error

# Configuration
PROJECT_ID="westside-la-events"
SERVICE_NAME="westside-events"
REGION="us-west1"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"
BUCKET_NAME="westside-la-events-data"

# Parse command line arguments
SKIP_TESTS=true  # Skip tests by default (use --run-tests to enable)
ROLLBACK=false
ENV_FILE=""
NO_CACHE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --run-tests)
            SKIP_TESTS=false
            shift
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --rollback)
            ROLLBACK=true
            shift
            ;;
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        --no-cache)
            NO_CACHE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: ./scripts/deploy.sh [--run-tests] [--rollback] [--env-file PATH] [--no-cache]"
            exit 1
            ;;
    esac
done

# Handle rollback
if [ "$ROLLBACK" = true ]; then
    echo "🔄 Rolling back to previous revision..."

    # Get the list of revisions
    REVISIONS=$(gcloud run revisions list \
        --service ${SERVICE_NAME} \
        --region ${REGION} \
        --format="value(name)" \
        --limit=2)

    # Get the previous revision (second in the list)
    PREV_REVISION=$(echo "$REVISIONS" | sed -n '2p')

    if [ -z "$PREV_REVISION" ]; then
        echo "❌ Error: No previous revision found to rollback to"
        exit 1
    fi

    echo "Rolling back to revision: ${PREV_REVISION}"

    gcloud run services update-traffic ${SERVICE_NAME} \
        --region ${REGION} \
        --to-revisions ${PREV_REVISION}=100

    echo "✅ Rollback complete!"
    exit 0
fi

echo "🚀 Deploying Westside LA Events to Google Cloud Run..."
echo ""

# Check if gcloud is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "❌ Error: Not authenticated with gcloud"
    echo "Run: gcloud auth login"
    exit 1
fi

# Set the project
echo "📋 Setting project to ${PROJECT_ID}..."
gcloud config set project ${PROJECT_ID}

# Pre-deployment checks
echo ""
echo "🔍 Running pre-deployment checks..."

# Check if Dockerfile exists
if [ ! -f "Dockerfile" ]; then
    echo "❌ Error: Dockerfile not found"
    exit 1
fi

# Check if required directories exist
if [ ! -d "src" ]; then
    echo "❌ Error: src/ directory not found"
    exit 1
fi

# Run tests (unless skipped)
if [ "$SKIP_TESTS" = false ]; then
    echo ""
    echo "🧪 Running tests..."

    # Check if micromamba is available
    if command -v micromamba &> /dev/null; then
        # Run basic unit tests (fast ones only) with clean environment
        # Use bash -c to unset PYTHONPATH and avoid ROS contamination
        if bash -c 'unset PYTHONPATH; PYTHONNOUSERSITE=1 micromamba run -n la python -m pytest tests/unit/ -v --tb=short'; then
            echo "✅ Tests passed"
        else
            echo "❌ Tests failed. Remove --run-tests to deploy without testing."
            exit 1
        fi
    else
        echo "⚠️  Warning: micromamba not found, skipping tests"
    fi
else
    echo "⏭️  Skipping tests (use --run-tests to run tests before deployment)"
fi

# Check git status
echo ""
echo "📊 Git status:"
if [ -d .git ]; then
    BRANCH=$(git rev-parse --abbrev-ref HEAD)
    COMMIT=$(git rev-parse --short HEAD)
    echo "  Branch: ${BRANCH}"
    echo "  Commit: ${COMMIT}"

    # Check for uncommitted changes
    if ! git diff-index --quiet HEAD --; then
        echo "  ⚠️  Warning: You have uncommitted changes"
        read -p "Continue deployment? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

# Download fresh database from Cloud Storage to bundle in Docker image
echo ""
echo "📥 Downloading fresh database for bundling..."
mkdir -p data

# Download events.db (required)
if gsutil -q stat "gs://${BUCKET_NAME}/events.db" 2>/dev/null; then
    echo "  Downloading events.db..."
    gsutil cp "gs://${BUCKET_NAME}/events.db" data/events.db
    DB_SIZE=$(ls -lh data/events.db | awk '{print $5}')
    echo "  ✓ Downloaded events.db (${DB_SIZE})"
else
    echo "  ⚠️  No events.db in Cloud Storage"
    if [ ! -f "data/events.db" ]; then
        echo "  ❌ Error: No local events.db found either"
        echo "  Run scrapers first: micromamba run -n la python run_scrapers.py"
        exit 1
    else
        echo "  Using existing local events.db"
    fi
fi

# Download analytics.db (optional)
if gsutil -q stat "gs://${BUCKET_NAME}/analytics.db" 2>/dev/null; then
    echo "  Downloading analytics.db..."
    gsutil cp "gs://${BUCKET_NAME}/analytics.db" data/analytics.db
    echo "  ✓ Downloaded analytics.db"
else
    echo "  ⚠️  No analytics.db in Cloud Storage (will start fresh)"
fi

# Download geocode_cache.json (optional)
if gsutil -q stat "gs://${BUCKET_NAME}/geocode_cache.json" 2>/dev/null; then
    echo "  Downloading geocode_cache.json..."
    gsutil cp "gs://${BUCKET_NAME}/geocode_cache.json" data/geocode_cache.json
    echo "  ✓ Downloaded geocode_cache.json"
else
    echo "  ⚠️  No geocode_cache.json in Cloud Storage"
fi

echo "✅ Database bundle ready for Docker build"

# Build the container image
echo ""
echo "🔨 Building container image..."
if [ "$NO_CACHE" = true ]; then
    echo "⚠️  No-cache mode: forcing clean rebuild (this will take longer)..."
    # Use standard Docker build without cache
    gcloud builds submit --tag ${IMAGE_NAME} --no-cache
else
    echo "Using Kaniko with layer caching for faster builds (typically 2-3 minutes)..."
    # Use cloudbuild.yaml with Kaniko for efficient caching
    if [ -f "cloudbuild.yaml" ]; then
        gcloud builds submit --config cloudbuild.yaml
    else
        echo "⚠️  cloudbuild.yaml not found, falling back to standard build..."
        gcloud builds submit --tag ${IMAGE_NAME}
    fi
fi

# Prepare environment variables
ENV_VARS="ENVIRONMENT=production,NTFY_TOPIC=westside-events-scraper"

# Add environment variables from file if provided
if [ -n "$ENV_FILE" ]; then
    if [ -f "$ENV_FILE" ]; then
        echo ""
        echo "📝 Loading environment variables from ${ENV_FILE}..."
        # Read env file and append to ENV_VARS (simple parsing, doesn't handle complex cases)
        while IFS='=' read -r key value; do
            # Skip comments and empty lines
            [[ $key =~ ^#.*$ ]] && continue
            [[ -z $key ]] && continue
            # Remove quotes from value
            value="${value%\"}"
            value="${value#\"}"
            ENV_VARS="${ENV_VARS},${key}=${value}"
        done < "$ENV_FILE"
    else
        echo "⚠️  Warning: Environment file ${ENV_FILE} not found, ignoring"
    fi
fi

# Deploy to Cloud Run
echo ""
echo "☁️  Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME} \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 300 \
    --set-env-vars "${ENV_VARS}" \
    --max-instances 10 \
    --min-instances 0

# Force traffic to the latest revision (workaround for Cloud Run sometimes
# not updating latestReady when new revision gets scaled to zero immediately)
NEW_REVISION=$(gcloud run revisions list \
    --service ${SERVICE_NAME} \
    --region ${REGION} \
    --format="value(name)" \
    --limit=1)
echo "  Routing 100% traffic to ${NEW_REVISION}..."
gcloud run services update-traffic ${SERVICE_NAME} \
    --region ${REGION} \
    --to-revisions ${NEW_REVISION}=100 --quiet

# Get the service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --region ${REGION} \
    --format 'value(status.url)')

# Verify deployment
echo ""
echo "🔍 Verifying deployment..."
sleep 5  # Give the service a moment to start

if curl -f -s -o /dev/null -w "%{http_code}" "${SERVICE_URL}" | grep -q "200\|301\|302"; then
    echo "✅ Service is responding"
else
    echo "⚠️  Warning: Service may not be responding correctly"
    echo "Check logs: gcloud run logs read ${SERVICE_NAME} --region ${REGION} --limit 50"
fi

# Set up Cloud Scheduler for daily scraping
echo ""
echo "⏰ Setting up Cloud Scheduler for daily scraping..."
SCHEDULER_JOB="scrape-daily"
SCRAPER_URL="${SERVICE_URL}/api/run-scrapers"

# Retrieve the SCRAPER_TOKEN from Secret Manager
SCRAPER_TOKEN=$(gcloud secrets versions access latest --secret=scraper-token 2>/dev/null || true)

if [ -z "$SCRAPER_TOKEN" ]; then
    echo "  ⚠️  Warning: SCRAPER_TOKEN secret not found in Secret Manager"
    echo "  Cloud Scheduler job will NOT be created."
    echo "  To fix: echo -n 'your-token' | gcloud secrets create scraper-token --data-file=-"
else
    # Check if the job already exists
    if gcloud scheduler jobs describe ${SCHEDULER_JOB} --location=${REGION} &>/dev/null; then
        echo "  Updating existing scheduler job..."
        gcloud scheduler jobs update http ${SCHEDULER_JOB} \
            --location=${REGION} \
            --schedule="0 12 * * *" \
            --time-zone="America/Los_Angeles" \
            --uri="${SCRAPER_URL}" \
            --http-method=POST \
            --headers="Authorization=Bearer ${SCRAPER_TOKEN}" \
            --attempt-deadline=600s \
            --quiet
    else
        echo "  Creating new scheduler job..."
        gcloud scheduler jobs create http ${SCHEDULER_JOB} \
            --location=${REGION} \
            --schedule="0 4 * * *" \
            --time-zone="America/Los_Angeles" \
            --uri="${SCRAPER_URL}" \
            --http-method=POST \
            --headers="Authorization=Bearer ${SCRAPER_TOKEN}" \
            --attempt-deadline=600s \
            --quiet
    fi
    echo "  ✅ Cloud Scheduler job '${SCHEDULER_JOB}' configured (daily at 4 AM PST)"
fi

# Display deployment info
echo ""
echo "✅ Deployment complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 Service URL: ${SERVICE_URL}"
echo "📦 Image: ${IMAGE_NAME}"
echo "🗄️  Storage: gs://${BUCKET_NAME}/"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Next steps:"
echo "  • Test the service:"
echo "    curl ${SERVICE_URL}"
echo ""
echo "  • View recent logs:"
echo "    gcloud run logs read ${SERVICE_NAME} --region ${REGION} --limit 50"
echo ""
echo "  • Monitor service:"
echo "    https://console.cloud.google.com/run/detail/${REGION}/${SERVICE_NAME}"
echo ""
echo "  • Rollback if needed:"
echo "    ./scripts/deploy.sh --rollback"
echo ""
echo "  • Check Cloud Storage:"
echo "    gsutil ls gs://${BUCKET_NAME}/"
echo ""
echo "  • Verify secrets (SCRAPER_TOKEN):"
echo "    gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format='value(spec.template.spec.containers[0].env)'"
