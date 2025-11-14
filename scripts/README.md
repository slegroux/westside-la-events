# Scripts Directory

This directory contains utility scripts and automation tools for the LA Events Aggregator project.

## Directory Structure

```
scripts/
├── *.py              # Core utility scripts (6 files)
└── *.sh              # GitHub workflow automation scripts (4 files)
```

## Deployment Scripts

### deploy.sh
**Purpose:** Deploy the application to Google Cloud Run

**Usage:**
```bash
# Standard deployment (runs tests first)
./scripts/deploy.sh

# Skip tests (faster, but less safe)
./scripts/deploy.sh --skip-tests

# Rollback to previous version
./scripts/deploy.sh --rollback

# Deploy with custom environment variables
./scripts/deploy.sh --env-file .env.production
```

**Features:**
- Pre-deployment checks (Dockerfile, src directory)
- Runs unit tests before deploying
- Checks git status and warns about uncommitted changes
- Builds Docker image via Google Cloud Build
- Deploys to Cloud Run with optimized settings
- Verifies deployment by checking service health
- Shows service URL and helpful next steps
- Supports rollback to previous revision

**Requirements:**
- Authenticated with gcloud (`gcloud auth login`)
- Correct project set (`gcloud config set project westside-events-406046958598`)

## Core Utility Scripts

These Python scripts handle database management, geocoding, and maintenance:

### Database Tools
- **inspect_db.py** - Quick database inspection and statistics
- **fix_database_triggers.py** - Fix database triggers and constraints

### Data Enhancement
- **geocode_missing.py** - Geocode events with missing coordinates (includes address improvements)
- **reclassify_all_events.py** - Reclassify all events in database using updated classifier
- **migrate_logos.py** - Migrate source logos to new format

### Testing
- **run_pytest.py** - Run pytest with proper configuration (essential for avoiding ROS conflicts)

**Usage Note:** All Python scripts should be run from the project root using:
```bash
micromamba run -n la python scripts/<script_name>.py
```

**Note:** Data quality checks (duplicates, locations, sources, logos) are now automated tests in [tests/unit/](../tests/unit/). Run them with `micromamba run -n la python -m pytest tests/unit/ -v`

## Testing Scrapers

For testing scrapers, use the proper pytest tests in [tests/scrapers/](../tests/scrapers/):

```bash
# Run all scraper tests
micromamba run -n la python -m pytest tests/scrapers/ -v

# Run tests for a specific scraper
micromamba run -n la python -m pytest tests/scrapers/test_kcrw.py -v

# Run only live integration tests (hits actual websites)
micromamba run -n la python -m pytest tests/scrapers/ -m requires_network -v
```

## GitHub Workflow Automation Scripts

These shell scripts help with GitHub issue tracking, milestones, and workflow automation:

### Available Scripts

### 1. daily-standup.sh
**Purpose:** Daily development standup report
**Usage:** `./scripts/daily-standup.sh`

Shows:
- Your assigned tasks
- High priority issues
- Recently closed issues (last 3 days)
- Milestone progress
- Quick action commands

**Recommended:** Run this every morning to start your day.

### 2. check-milestone-progress.sh
**Purpose:** View progress for all milestones
**Usage:** `./scripts/check-milestone-progress.sh`

Shows:
- Milestone names
- Open vs closed issues
- Completion percentage

**Recommended:** Run weekly to track progress.

### 3. weekly-report.sh
**Purpose:** Generate weekly issue activity report
**Usage:** `./scripts/weekly-report.sh`

Shows:
- Issues closed this week
- Issues created this week
- Open high priority issues

**Recommended:** Run at end of week for retrospective.

### 4. feature-done-checklist.sh
**Purpose:** Feature completion checklist
**Usage:** `./scripts/feature-done-checklist.sh <issue-number>`

Shows:
- Pre-merge checklist
- Post-merge checklist
- Verification commands

**Recommended:** Run before closing any feature issue.

## Example Workflows

### Starting Your Day
```bash
# Check what you need to work on today
./scripts/daily-standup.sh

# Pick an issue and start working
gh issue view 32
git checkout -b feature/deduplication-#32
```

### Completing a Feature
```bash
# Review completion checklist
./scripts/feature-done-checklist.sh 32

# Create PR
gh pr create --title "Implement event deduplication" \
  --body "Closes #32" \
  --milestone "Phase 2: Enhancement"
```

### Weekly Review
```bash
# Generate weekly report
./scripts/weekly-report.sh

# Check milestone progress
./scripts/check-milestone-progress.sh
```

## Git Hooks

### prepare-commit-msg
Located at `.git/hooks/prepare-commit-msg`

Warns if your commit message doesn't reference an issue. This helps maintain traceability between code changes and issues.

**Triggered:** On every commit
**Action:** Warns (but allows) commits without issue references

## Automation

### GitHub Actions
Located at `.github/workflows/issue-tracking.yml`

Automates:
- Milestone progress comments when issues close
- Label checks on new issues
- Auto-labeling PRs based on changed files
- Linking related issues

**Triggered:** When issues/PRs are opened or closed

## Quick Reference

```bash
# View your assigned issues
gh issue list --assignee @me

# View milestone issues
gh issue list --milestone "Phase 1: MVP"

# Create new issue with milestone
gh issue create --title "Add dark mode" \
  --body "Implement dark mode toggle" \
  --milestone "Phase 3: Polish" \
  --label "type: feature,priority: medium"

# Close issue with comment
gh issue close 32 --comment "Implemented and tested"

# View specific issue
gh issue view 32
```

## Setup

All scripts should already be executable. If not:

```bash
chmod +x scripts/*.sh
```

## Requirements

- `gh` (GitHub CLI) - Install: https://cli.github.com/
- `jq` (JSON processor) - Install: `sudo apt install jq`
- `python` (for JSON formatting)

## Troubleshooting

**"gh: command not found"**
- Install GitHub CLI: https://cli.github.com/

**"jq: command not found"**
- Install jq: `sudo apt install jq`

**"Permission denied"**
- Make script executable: `chmod +x scripts/<script-name>.sh`

## Contributing

When adding new scripts:
1. Add them to this directory
2. Make them executable: `chmod +x scripts/<script>.sh`
3. Document them in this README
4. Update GITHUB_WORKFLOW.md if they affect the workflow
