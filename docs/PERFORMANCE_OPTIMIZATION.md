# Performance Optimization: Bundled Database Strategy

## Problem

**Initial cold start time: 3-5 seconds**

The application had slow cold start times on Google Cloud Run due to:

1. **Cloud Storage Downloads** (2-3 seconds)
   - Every container startup downloaded database from Cloud Storage
   - Multiple `gsutil cp` operations for `events.db`, `analytics.db`, `geocode_cache.json`
   - Network latency on every cold start

2. **Scale-to-Zero Architecture**
   - Cloud Run shuts down containers after ~15 minutes of inactivity
   - Each user visit after idle period triggers cold start
   - No minimum instances = frequent cold starts

3. **Large Initial Page Load** (295KB HTML)
   - Home page rendered 100 events on initial load
   - Full event cards with images, descriptions, etc.

## Solution: Bundled Database

### Strategy

Instead of downloading the database on every container startup, we now **bundle the database inside the Docker image** during build time.

### Implementation

#### 1. Dockerfile Changes

```dockerfile
# Copy bundled database files if they exist (for faster cold starts)
RUN if [ -f data/events.db ]; then cp data/events.db /app/data/events.db; fi && \
    if [ -f data/analytics.db ]; then cp data/analytics.db /app/data/analytics.db; fi && \
    if [ -f data/geocode_cache.json ]; then cp data/geocode_cache.json /app/data/geocode_cache.json; fi

# Set environment variable to skip downloads
ENV SKIP_DB_DOWNLOAD=true
```

#### 2. Entrypoint Changes

The `entrypoint.sh` now checks `SKIP_DB_DOWNLOAD` and skips Cloud Storage downloads by default:

```bash
if [ "$SKIP_DB_DOWNLOAD" = "true" ]; then
    echo "⚡ Using bundled database (fast startup mode)"
else
    # Download from Cloud Storage (fallback mode)
    ...
fi
```

#### 3. Deployment Script Changes

The `scripts/deploy.sh` now:
1. Downloads fresh database from Cloud Storage
2. Bundles it into the Docker image during build
3. Deploys the image with bundled data

```bash
# Download fresh database for bundling
gsutil cp "gs://${BUCKET_NAME}/events.db" data/events.db
gsutil cp "gs://${BUCKET_NAME}/analytics.db" data/analytics.db
gsutil cp "gs://${BUCKET_NAME}/geocode_cache.json" data/geocode_cache.json

# Build Docker image (will include bundled data)
docker build -t westside-events .
```

### Expected Performance Gains

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Cold start time** | 3-5 seconds | 0.5-1 second | **80-83% faster** |
| **Database download** | 2-3 seconds | 0 seconds | **Eliminated** |
| **Container startup** | Download every time | Use bundled data | **Instant** |

## Deployment Workflow

### Normal Deployment (Code + Data Updates)

```bash
# This automatically downloads fresh data and bundles it
./scripts/deploy.sh
```

The deployment script:
1. ✓ Downloads latest database from Cloud Storage
2. ✓ Bundles it in Docker image
3. ✓ Builds and deploys to Cloud Run
4. ✓ Container starts instantly with bundled data

### Data-Only Updates

If you just want to update the production database without deploying code:

```bash
# Run scrapers and sync to Cloud Storage
./scripts/sync_db_to_cloud.sh --run-scrapers --force

# Then deploy to bundle the fresh data
./scripts/deploy.sh
```

### Force Cloud Storage Download (Emergency)

If you need containers to download from Cloud Storage (e.g., urgent data update without redeployment):

```bash
gcloud run services update westside-events \
  --region us-west1 \
  --set-env-vars SKIP_DB_DOWNLOAD=false
```

**Note**: This reverts to the slow startup mode. Redeploy to restore fast mode.

## Trade-offs

### Advantages ✅
- **Much faster cold starts** (80% improvement)
- **Lower Cloud Storage costs** (fewer API calls)
- **Better user experience** (instant page loads)
- **Simpler architecture** (no runtime downloads)

### Disadvantages ⚠️
- **Data is snapshot-based**: Database reflects state at build time
- **Requires redeployment** to update data (takes ~5 minutes)
- **Slightly larger Docker images** (~5-10MB larger)

### Why This Works For Us

This is an excellent trade-off for our use case because:
- Events data changes **slowly** (once daily via scheduled scraper)
- We already deploy regularly
- Cold start performance is critical for user experience
- Cloud Storage costs scale with usage

## Alternative Solutions Considered

### 1. Set Minimum Instances (minScale=1)
```bash
gcloud run services update westside-events --min-instances=1
```

**Pros**: Always warm, instant response
**Cons**: ~$15-30/month idle container cost
**Decision**: Not worth it for low-traffic app

### 2. Cloud SQL
**Pros**: Always available, no cold start issues
**Cons**: $25-50+/month minimum
**Decision**: Too expensive for MVP

### 3. Keep Current Approach
**Pros**: Simplest code
**Cons**: Poor user experience (3-5s cold starts)
**Decision**: Unacceptable UX

## Monitoring

### Check Startup Time

```bash
# View recent startup logs
gcloud run logs read westside-events --region us-west1 \
  --filter="textPayload=~\"Starting Westside\"" --limit=10

# Should see: "⚡ Using bundled database (fast startup mode)"
```

### Verify Database Bundle

```bash
# Check if database is bundled in running container
gcloud run services proxy westside-events --region us-west1 &
curl localhost:8080/admin/db-info
```

## Future Optimizations

1. **Reduce initial page load** (from 295KB)
   - Load only 12-20 events initially
   - Implement lazy loading / infinite scroll
   - Defer non-critical JavaScript

2. **Enable compression**
   - Add gzip/brotli middleware
   - Should reduce 295KB → ~50KB

3. **Add CDN caching**
   - Cache static assets on Cloud CDN
   - Cache anonymous home page for 5 minutes

4. **Optimize event cards**
   - Lazy load images
   - Use smaller thumbnails
   - Defer favorite button rendering

## References

- [Dockerfile](../Dockerfile#L47-L52) - Database bundling logic
- [entrypoint.sh](../entrypoint.sh#L5-L10) - Skip download logic
- [scripts/deploy.sh](../scripts/deploy.sh#L163-L203) - Pre-build data download
- [.dockerignore](../.dockerignore#L46-L49) - Include data directory
