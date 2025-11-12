# Deploying to Railway

This guide walks you through deploying the Westside LA Events Aggregator to Railway.app.

## Prerequisites

1. A [Railway.app account](https://railway.app/) (free tier available)
2. [Railway CLI](https://docs.railway.app/guides/cli) installed (optional, but recommended)
3. Your project pushed to a Git repository (GitHub, GitLab, or Bitbucket)

## Quick Deploy (Web Interface)

### Step 1: Create a New Project

1. Go to [Railway.app](https://railway.app/) and log in
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose your repository (you may need to authorize Railway to access your GitHub)
5. Select the branch you want to deploy (usually `main` or `master`)

### Step 2: Configure Environment Variables

Railway will automatically detect the Python project. Now configure environment variables:

1. In your Railway project dashboard, go to the **Variables** tab
2. Add the following environment variables (all are optional, but recommended):

```bash
# Required for production
DEBUG=False

# Database path (Railway will create this automatically)
DATABASE_PATH=/app/data/events.db

# Optional: Google API keys for geocoding
GOOGLE_GEOCODING_API_KEY=your_key_here

# Logging
LOG_LEVEL=INFO
LOG_FILE=/tmp/app.log
```

**Important Notes:**
- Railway automatically sets the `PORT` environment variable - don't override it
- The `DATABASE_PATH` should point to a persistent volume (see Step 3)
- Set `DEBUG=False` for production

### Step 3: Add Persistent Storage for Database

Railway's filesystem is ephemeral by default. To persist your SQLite database:

1. In your project dashboard, click **"Add Service"** → **"Volume"**
2. Click **"Add Volume"**
3. Name it: `data`
4. Mount path: `/app/data`
5. Click **"Add Volume"**

This creates persistent storage for your database at `/app/data/events.db`.

### Step 4: Deploy

Railway will automatically deploy your application. Monitor the deployment logs:

1. Go to the **Deployments** tab
2. Click on the latest deployment to see live logs
3. Wait for the build and deployment to complete (usually 2-5 minutes)

### Step 5: Access Your Application

1. Go to the **Settings** tab
2. Under **Networking**, click **"Generate Domain"**
3. Railway will create a public URL like `https://your-app.up.railway.app`
4. Click the URL to access your deployed application

## Deploy via Railway CLI

If you have the Railway CLI installed:

```bash
# Login to Railway
railway login

# Link to your project (first time only)
railway link

# Add environment variables
railway variables set DEBUG=False
railway variables set DATABASE_PATH=/app/data/events.db

# Deploy
railway up
```

## Initial Data Setup

After deployment, you'll need to populate the database with events:

### Option 1: Run Scrapers Manually (Recommended)

1. In Railway dashboard, go to your service
2. Click on the **"..."** menu → **"Shell"** to open a terminal
3. Run the scrapers:

```bash
python run_scrapers.py
```

### Option 2: Schedule Automatic Scraping

Railway doesn't have built-in cron jobs, but you can:

1. Use Railway's **Cron Jobs** feature (in beta):
   - Add a new service → Cron Job
   - Schedule: `0 3 * * *` (daily at 3 AM)
   - Command: `python run_scrapers.py`

2. Or use an external service like:
   - [GitHub Actions](https://github.com/features/actions) to trigger scraping
   - [EasyCron](https://www.easycron.com/) to hit an API endpoint
   - [Railway Cron](https://docs.railway.app/reference/cron-jobs)

## Monitoring and Troubleshooting

### View Logs

```bash
# Via CLI
railway logs

# Or in the Railway dashboard → Deployments → Click deployment → Logs
```

### Common Issues

**1. Application crashes on startup**
- Check logs for Python dependency errors
- Ensure all required files are committed to Git
- Verify environment variables are set correctly

**2. Database not persisting between deploys**
- Ensure you've added a volume at `/app/data`
- Verify `DATABASE_PATH` points to the volume: `/app/data/events.db`

**3. Port binding errors**
- Railway automatically sets `PORT` - don't override it
- The `Procfile` uses `$PORT` which Railway provides

**4. Static files not loading**
- Ensure `static/` directory is in your Git repository
- Check that `.gitignore` doesn't exclude static files

**5. Module import errors**
- Make sure `requirements.txt` includes all dependencies
- Check that Python version is compatible (Python 3.9+ required)

### Database Migrations

To access your production database:

```bash
# Open a shell in Railway
railway shell

# Access the SQLite database
sqlite3 /app/data/events.db

# Or run Python scripts
python -c "from src.data.database import Database; db = Database('/app/data/events.db'); print(db.get_event_count())"
```

## Updating the Application

Railway automatically redeploys when you push to your connected Git branch:

```bash
# Make your changes locally
git add .
git commit -m "Update feature"
git push origin main

# Railway will automatically detect the push and redeploy
```

## Cost Estimation

Railway's **Free Tier** includes:
- 500 hours of usage per month (enough for 1 service running 24/7)
- 5GB storage
- 100GB bandwidth

For most personal projects, this is more than sufficient. If you exceed limits, Railway's **Hobby Plan** ($5/month) provides:
- Unlimited usage hours
- 100GB storage
- 1TB bandwidth

## Scaling and Performance

Once your app is popular:

1. **Horizontal Scaling**: Railway can run multiple instances
2. **Database**: Consider migrating to PostgreSQL for better performance
3. **CDN**: Use Railway's built-in CDN for static files
4. **Caching**: Add Redis for caching scraped data

## Security Considerations

1. **Never commit `.env` files** - Use Railway environment variables
2. **Set `DEBUG=False`** in production
3. **Use HTTPS** - Railway provides this automatically
4. **Rate Limiting**: Consider adding rate limiting to your API endpoints
5. **API Keys**: Store sensitive keys in Railway environment variables

## Alternative Deployment Options

If Railway doesn't meet your needs:

- **Fly.io**: Similar to Railway, good SQLite support
- **Render.com**: Free tier with automatic SSL
- **PythonAnywhere**: Python-focused hosting
- **DigitalOcean App Platform**: More control, slightly more expensive
- **Heroku**: Established platform, limited free tier

## Support

- Railway Docs: https://docs.railway.app/
- Railway Discord: https://discord.gg/railway
- Project Issues: [Your GitHub Issues Link]

## Next Steps

After successful deployment:

1. ✅ Test all functionality on the live site
2. ✅ Set up monitoring and alerting
3. ✅ Configure automatic scraping schedule
4. ✅ Add your custom domain (Railway supports this)
5. ✅ Set up error tracking (e.g., Sentry)
6. ✅ Configure SSL certificate (automatic with Railway)

Happy deploying! 🚀
