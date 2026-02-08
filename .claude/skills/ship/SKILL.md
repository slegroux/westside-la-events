---
name: ship
description: Use when the user wants to deploy to production. Also use when the user says "ship it", "deploy", "ship to prod", or "deploy to production". For commit+push without deploying, use /push instead.
---

# /ship - Deploy to production

You are running the **ship** workflow. This deploys the current code and data to production. It does NOT run tests or commit/push — use `/test` and `/push` first.

## Important context
- Use `conda run -n la` for all commands (NOT micromamba)
- Production is on Google Cloud Run
- Database is synced to Cloud Storage

---

## Step 1: Pre-flight Check

Verify the repo is ready to deploy:

1. `git status` - check for uncommitted changes
2. `git log origin/master..HEAD --oneline` - check for unpushed commits

If there are uncommitted changes or unpushed commits, warn the user and suggest running `/push` first. Ask if they want to proceed anyway or push first.

---

## Step 2: Sync Database

Upload the latest local database to Cloud Storage:

```
conda run -n la bash scripts/sync_db_to_cloud.sh --force
```

Report the result. If it fails, stop and show the error.

---

## Step 3: Deploy Code

Deploy the application to Cloud Run:

```
conda run -n la bash scripts/deploy.sh
```

Report the result. If it fails, stop and show the error.

---

## Output Summary

At the end, print a clear summary:

```
## Ship Summary
- Database sync: success / failed
- Code deploy: success / failed
- Service URL: https://westside-events-406046958598.us-west1.run.app
```
