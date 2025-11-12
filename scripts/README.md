# Automation Scripts

This directory contains automation scripts for tracking GitHub issues, milestones, and ensuring proper workflow.

## Available Scripts

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
