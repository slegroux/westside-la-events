# Deployment Guide

This guide covers deploying the Westside LA Events application to various hosting platforms.

## Table of Contents
- [Google Cloud Run (Recommended)](#google-cloud-run-recommended)
- [Railway](#railway)
- [Other Options](#other-options)

---

## Google Cloud Run (Recommended)

Google Cloud Run is the recommended deployment platform for this application. It offers:
- **Free tier**: 2 million requests/month
- **Serverless**: Scales to zero when idle (~500ms wake time)
- **Persistent storage**: Cloud Storage for SQLite databases
- **Automated scraping**: Cloud Scheduler for daily scraper runs
- **Cost**: $0/month within free tier limits

### Prerequisites

1. Google Cloud account
2. Active billing account (required even for free tier, but you won't be charged)
3. `gcloud` CLI installed

### Step 1: Install Google Cloud SDK

```bash
# Download and install
curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-linux-x86_64.tar.gz
tar -xf google-cloud-cli-linux-x86_64.tar.gz
./google-cloud-sdk/install.sh --quiet

# Add to PATH (or restart shell)
export PATH="$HOME/google-cloud-sdk/bin:$PATH"

# Verify installation
gcloud --version
```

### Step 2: Authenticate and Create Project

```bash
# Login to Google Cloud
gcloud auth login

# Create a new project
gcloud projects create westside-la-events --name="Westside LA Events"

# Set as default project
gcloud config set project westside-la-events

# Link billing account (replace with your billing account ID)
gcloud beta billing accounts list
gcloud beta billing projects link westside-la-events --billing-account=YOUR_BILLING_ACCOUNT_ID

# Enable required APIs
gcloud services enable run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  storage-api.googleapis.com \
  cloudscheduler.googleapis.com
```

### Step 3: Set Up Persistent Storage

```bash
# Create Cloud Storage bucket for persistent data
gcloud storage buckets create gs://westside-la-events-data \
  --location=us-west1 \
  --uniform-bucket-level-access

# Upload existing data (optional)
gcloud storage cp data/*.db gs://westside-la-events-data/
gcloud storage cp data/geocode_cache.json gs://westside-la-events-data/
```

### Step 4: Deploy Application

```bash
# From project root directory
gcloud run deploy westside-events \
  --source . \
  --platform managed \
  --region us-west1 \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 1 \
  --memory 1Gi \
  --execution-environment gen2 \
  --add-volume name=data,type=cloud-storage,bucket=westside-la-events-data \
  --add-volume-mount volume=data,mount-path=/app/data \
  --set-env-vars SCRAPER_TOKEN=secure-$(openssl rand -hex 16)
```

**Note**: Save the `SCRAPER_TOKEN` value that's generated - you'll need it for the scheduler.

### Step 5: Configure Automated Scraping

```bash
# Create Cloud Scheduler job (runs daily at 4 AM PST / 12 PM UTC)
gcloud scheduler jobs create http scrape-westside-events \
  --location us-west1 \
  --schedule="0 12 * * *" \
  --time-zone="America/Los_Angeles" \
  --uri="https://YOUR_SERVICE_URL/api/run-scrapers" \
  --http-method=POST \
  --headers="Authorization=Bearer YOUR_SCRAPER_TOKEN" \
  --description="Run event scrapers daily at 4 AM PST"

# Test the scheduler manually
gcloud scheduler jobs run scrape-westside-events --location us-west1
```

Replace:
- `YOUR_SERVICE_URL` with your Cloud Run service URL (e.g., `https://westside-events-xxxxx.us-west1.run.app`)
- `YOUR_SCRAPER_TOKEN` with the token generated in Step 4

---

## Managing Your Deployment

### View Logs

```bash
# Tail logs in real-time
gcloud run logs tail westside-events --region us-west1

# View recent logs
gcloud run logs read westside-events --region us-west1 --limit 100
```

### Update Application

```bash
# Redeploy with latest code
gcloud run deploy westside-events \
  --source . \
  --region us-west1
```

### Manage Scheduler

```bash
# List scheduled jobs
gcloud scheduler jobs list --location us-west1

# Update schedule (e.g., run twice daily at 2 AM and 2 PM)
gcloud scheduler jobs update http scrape-westside-events \
  --location us-west1 \
  --schedule="0 2,14 * * *"

# Pause scheduler
gcloud scheduler jobs pause scrape-westside-events --location us-west1

# Resume scheduler
gcloud scheduler jobs resume scrape-westside-events --location us-west1

# Delete scheduler job
gcloud scheduler jobs delete scrape-westside-events --location us-west1
```

### Manage Storage

```bash
# List files in bucket
gcloud storage ls gs://westside-la-events-data/

# Download database backup
gcloud storage cp gs://westside-la-events-data/events.db \
  ./events_backup_$(date +%Y%m%d).db

# Upload updated database
gcloud storage cp data/events.db gs://westside-la-events-data/events.db
```

### Environment Variables

```bash
# View current environment variables
gcloud run services describe westside-events --region us-west1 \
  --format="value(spec.template.spec.containers[0].env)"

# Update environment variables
gcloud run services update westside-events --region us-west1 \
  --update-env-vars KEY=VALUE,KEY2=VALUE2

# Remove environment variables
gcloud run services update westside-events --region us-west1 \
  --remove-env-vars KEY1,KEY2
```

---

## Custom Domain Setup

### Using Google Cloud

```bash
# Map custom domain to your service
gcloud beta run domain-mappings create \
  --service westside-events \
  --domain yourdomain.com \
  --region us-west1
```

Then update your DNS:
1. Go to your domain registrar (e.g., Cloudflare, Namecheap)
2. Add the CNAME records provided by Google Cloud
3. Wait for DNS propagation (5-60 minutes)

---

## Monitoring and Costs

### View Usage

```bash
# View service details
gcloud run services describe westside-events --region us-west1

# View metrics in console
# https://console.cloud.google.com/run/detail/us-west1/westside-events/metrics
```

### Cost Management

**Free Tier Limits:**
- Cloud Run: 2 million requests/month, 360,000 GB-seconds of memory, 180,000 vCPU-seconds
- Cloud Storage: 5 GB storage, 1 GB network egress
- Cloud Scheduler: 3 jobs
- Cloud Build: 120 build-minutes/day

**Set Budget Alerts:**
1. Go to https://console.cloud.google.com/billing/budgets
2. Create budget with alerts at 50%, 90%, 100%
3. Add your email for notifications

**Monitor Costs:**
```bash
# View current month's costs
gcloud billing accounts list
# Then view in console: https://console.cloud.google.com/billing
```

---

## Railway

Railway offers a simpler deployment experience with GitHub integration.

### Prerequisites

1. Push your code to GitHub
2. Create a Railway account at https://railway.app

### Deployment Steps

1. **Create New Project**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your repository

2. **Configure Build**
   - Railway auto-detects the Dockerfile
   - No configuration needed

3. **Environment Variables**
   - Add any required environment variables in the Railway dashboard
   - Railway automatically provides `PORT` variable

4. **Deploy**
   - Railway automatically deploys on every push to main branch
   - Get your public URL from the Railway dashboard

### Configuration Files

The project includes Railway configuration files:

**railway.json**
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "numReplicas": 1,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

**Procfile**
```
web: uvicorn src.web.app:app --host 0.0.0.0 --port $PORT
```

### Railway Free Tier

- **$5 credit** per month
- **500 hours** of usage (~20 days)
- Automatically sleeps when out of credit
- No credit card required for trial

---

## Other Options

### Fly.io

Similar to Railway but with:
- CLI-first deployment
- ~300ms wake time
- ~$1.94/month for always-on

### Render

- Easy deployment
- Free tier available (sleeps after 15 min)
- ~15-30s wake time
- $7/month for always-on

### DigitalOcean App Platform

- $5/month minimum
- Always running
- Good for production
- Includes database options

---

## Troubleshooting

### Deployment Fails

**Issue**: Build fails with dependency errors
```bash
# Check logs
gcloud run logs read westside-events --region us-west1 --limit 100

# Common fixes:
# 1. Ensure Dockerfile is correct
# 2. Check requirements.txt has all dependencies
# 3. Verify Python version compatibility
```

**Issue**: Service starts but crashes
```bash
# Check startup logs
gcloud run logs tail westside-events --region us-west1

# Common issues:
# - Missing environment variables
# - Database connection errors
# - Port binding (ensure using $PORT)
```

### Scheduler Not Running

```bash
# Check scheduler status
gcloud scheduler jobs describe scrape-westside-events --location us-west1

# View scheduler logs
gcloud logging read "resource.type=cloud_scheduler_job AND \
  resource.labels.job_id=scrape-westside-events" --limit 50

# Test manually
gcloud scheduler jobs run scrape-westside-events --location us-west1
```

### Storage Issues

```bash
# Verify bucket exists
gcloud storage ls

# Check bucket permissions
gcloud storage buckets describe gs://westside-la-events-data

# Fix permissions if needed
gcloud storage buckets add-iam-policy-binding gs://westside-la-events-data \
  --member=serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com \
  --role=roles/storage.objectAdmin
```

### Database Not Persisting

**Issue**: Data resets on container restart

**Fix**: Ensure Cloud Storage is properly mounted:
```bash
# Check service configuration
gcloud run services describe westside-events --region us-west1 \
  --format="value(spec.template.spec.volumes)"

# Should show cloud-storage volume mounted
```

---

## Security Best Practices

### Secure Scraper Endpoint

The `/api/run-scrapers` endpoint is protected with a bearer token:

```python
# In src/web/app.py
auth_header = request.headers.get('Authorization', '')
expected_token = os.getenv('SCRAPER_TOKEN', 'default-secret-token')

if auth_header != f'Bearer {expected_token}':
    return JSONResponse({'error': 'Unauthorized'}, status_code=401)
```

**Regenerate token if compromised:**
```bash
# Generate new token
NEW_TOKEN="secure-$(openssl rand -hex 16)"

# Update Cloud Run
gcloud run services update westside-events --region us-west1 \
  --update-env-vars SCRAPER_TOKEN=$NEW_TOKEN

# Update Cloud Scheduler
gcloud scheduler jobs update http scrape-westside-events \
  --location us-west1 \
  --headers="Authorization=Bearer $NEW_TOKEN"
```

### Restrict Access

For admin endpoints, consider:
- Using Cloud IAM for authentication
- Adding IP allowlists
- Implementing rate limiting

---

## Production Checklist

Before going live:

- [ ] Custom domain configured with SSL
- [ ] Budget alerts set up
- [ ] Monitoring configured
- [ ] Backup strategy for database
- [ ] Error tracking set up (e.g., Sentry)
- [ ] Analytics configured
- [ ] Scraper schedule tested and verified
- [ ] Environment variables secured
- [ ] Documentation updated
- [ ] Performance tested under load

---

## Support

For deployment issues:
- **Google Cloud**: https://cloud.google.com/support
- **Railway**: https://help.railway.app
- **Project Issues**: https://github.com/YOUR_USERNAME/LA/issues
