# Issue Tracking Quick Start

Get started with GitHub issue tracking in 5 minutes.

## Initial Setup (One Time)

### 1. Verify GitHub CLI is Installed
```bash
gh --version
# If not installed: https://cli.github.com/
```

### 2. Authenticate GitHub CLI
```bash
gh auth login
```

### 3. Test the Scripts
```bash
# Daily standup report
./scripts/daily-standup.sh

# Milestone progress
./scripts/check-milestone-progress.sh
```

## Daily Workflow

### Morning Routine (2 minutes)
```bash
# See what you need to do today
./scripts/daily-standup.sh

# Pick an issue to work on
gh issue list --assignee @me

# Or pick from high priority
gh issue list --label "priority: high"

# View the issue details
gh issue view 42
```

### Starting a New Feature (1 minute)
```bash
# Create a branch named after the issue
git checkout -b feature/dark-mode-#42

# Start coding!
```

### During Development
```bash
# Commit with issue reference
git commit -m "Add dark mode toggle

Part of #42"

# Or for bug fixes
git commit -m "Fix button alignment

Fixes #43"
```

### Completing a Feature (3 minutes)
```bash
# Check completion checklist
./scripts/feature-done-checklist.sh 42

# Run tests
env -u PYTHONPATH -u AMENT_PREFIX_PATH -u ROS_DISTRO PYTHONNOUSERSITE=1 micromamba run -n la python -m pytest tests/

# Create PR that automatically closes the issue
gh pr create \
  --title "Add dark mode toggle" \
  --body "Closes #42"

# After PR is merged, verify issue closed
gh issue view 42
```

### Weekly Review (5 minutes)
```bash
# Friday afternoon - review the week
./scripts/weekly-report.sh

# Check milestone progress
./scripts/check-milestone-progress.sh
```

## Common Tasks

### Create a New Issue
```bash
# Using interactive mode
gh issue create

# Or with all details
gh issue create \
  --title "[FEATURE] Add calendar export" \
  --body "Allow users to export events to iCal format" \
  --milestone "Future Enhancements" \
  --label "type: feature,priority: low"
```

### Update an Existing Issue
```bash
# Assign to yourself
gh issue edit 42 --add-assignee @me

# Change milestone
gh issue edit 42 --milestone "Phase 3: Polish"

# Add labels
gh issue edit 42 --add-label "priority: high"
```

### Search for Issues
```bash
# Search by keyword
gh issue list --search "dark mode"

# Filter by label
gh issue list --label "area: frontend"

# Filter by milestone
gh issue list --milestone "Phase 1: MVP"

# Combine filters
gh issue list --label "priority: high" --milestone "Phase 1: MVP"
```

### Close an Issue Manually
```bash
# With a comment
gh issue close 42 --comment "Implemented and tested in PR #123"

# Reopen if needed
gh issue reopen 42
```

## Pro Tips

### 1. Use Closing Keywords in Commits
These keywords in commit messages or PR descriptions will automatically close issues when merged to main:

✅ **Closes** #42
✅ **Fixes** #42
✅ **Resolves** #42

❌ **Part of** #42 (links but doesn't close)
❌ **Relates to** #42 (links but doesn't close)

### 2. Multiple Issues in One PR
```bash
gh pr create --body "Closes #42, closes #43, closes #44"
```

### 3. Reference Issues Across Repos
```bash
# Link to issue in another repo
gh pr create --body "Closes owner/other-repo#123"
```

### 4. Use Issue Templates
When creating issues on GitHub web:
- Click "New Issue"
- Choose template: Feature, Bug, Scraper, or Test
- Fill in the template

### 5. Keyboard Shortcuts on GitHub
- `C` - Create new issue
- `G I` - Go to issues
- `/` - Focus search
- `Ctrl+K` - Command palette

### 6. Set Up Notifications
Configure at: https://github.com/settings/notifications

Recommended:
- ✅ Participating and @mentions
- ✅ Issues and PRs you're assigned to
- ❌ All activity (too noisy)

## Troubleshooting

### Issue Didn't Auto-Close After PR Merge?

**Problem:** PR merged but issue still open

**Solutions:**
1. Check if "Closes #N" was in PR description (not just commits)
2. Manually close: `gh issue close N --comment "Closed by PR #M"`
3. Verify you merged to `main` branch (auto-close only works on default branch)

### Commit Message Doesn't Reference Issue?

**Problem:** Forgot to add "Part of #42" in commit

**Solutions:**
1. Amend last commit: `git commit --amend`
2. Or reference in PR description instead
3. Or add issue reference in next commit

### Wrong Milestone or Labels?

**Problem:** Issue assigned to wrong milestone

**Solutions:**
```bash
# Change milestone
gh issue edit 42 --milestone "Phase 2: Enhancement"

# Add label
gh issue edit 42 --add-label "priority: high"

# Remove label
gh issue edit 42 --remove-label "priority: low"
```

### Can't Find an Issue?

**Problem:** Looking for a specific issue

**Solutions:**
```bash
# Search by keyword
gh issue list --search "deduplication"

# Search closed issues too
gh issue list --state all --search "deduplication"

# View all issues (open and closed)
gh issue list --state all
```

## Integration with PLAN.md

Keep [PLAN.md](../PLAN.md) and GitHub issues in sync:

1. **PLAN.md** = Task checkboxes and implementation details
2. **GitHub Issues** = Tracking, discussion, and closure

**Workflow:**
1. Check off task in PLAN.md when complete
2. Create commit referencing issue: `git commit -m "... Closes #42"`
3. Issue automatically closes when PR merges
4. GitHub Action comments with milestone progress

## What Gets Automated

You don't need to do these manually:

✅ Issue closes when PR with "Closes #N" merges
✅ Milestone progress comment added to closed issues
✅ PRs auto-labeled based on changed files
✅ Commit hook warns about missing issue references

You still need to do:

📝 Create issues for new features/bugs
📝 Assign milestones to issues
📝 Reference issues in commits/PRs
📝 Update PLAN.md checkboxes
📝 Update documentation

## Example: Complete Feature Flow

Let's walk through adding a "dark mode" feature:

### 1. Create Issue
```bash
gh issue create \
  --title "[FEATURE] Add dark mode toggle" \
  --body "Implement dark mode with toggle in settings" \
  --milestone "Phase 3: Polish" \
  --label "type: feature,priority: medium,area: frontend"

# Returns: Created issue #42
```

### 2. Start Work
```bash
# Create feature branch
git checkout -b feature/dark-mode-#42

# Start coding...
```

### 3. Make Commits
```bash
# First commit
git commit -m "Add dark mode CSS variables

Part of #42"

# Second commit
git commit -m "Add dark mode toggle component

Part of #42"

# Third commit
git commit -m "Add dark mode state persistence

Part of #42"
```

### 4. Push and Create PR
```bash
git push -u origin feature/dark-mode-#42

gh pr create \
  --title "Add dark mode toggle" \
  --body "Implements dark mode with CSS variables and localStorage persistence.

Closes #42"
```

### 5. Review and Merge
```bash
# After review, merge the PR
gh pr merge --squash

# Or merge via GitHub web UI
```

### 6. Verify Closure
```bash
# Check that issue auto-closed
gh issue view 42
# Should show: STATE: CLOSED

# Check milestone progress
./scripts/check-milestone-progress.sh
```

### 7. Update Documentation
```bash
# Update PLAN.md checkbox
# Update README if user-facing feature
git commit -m "Update docs for dark mode feature

Relates to #42"
```

Done! 🎉

## Next Steps

- **Detailed Guide:** Read [docs/GITHUB_WORKFLOW.md](GITHUB_WORKFLOW.md)
- **Visual Summary:** Read [docs/TRACKING_SUMMARY.md](TRACKING_SUMMARY.md)
- **Script Docs:** Read [scripts/README.md](../scripts/README.md)

## Quick Reference Card

Print this and keep it nearby:

```
DAILY:
  ./scripts/daily-standup.sh
  gh issue list --assignee @me

STARTING:
  git checkout -b feature/name-#42

COMMITTING:
  git commit -m "..."
  Part of #42

FINISHING:
  gh pr create --body "Closes #42"

WEEKLY:
  ./scripts/weekly-report.sh
  ./scripts/check-milestone-progress.sh

CLOSING KEYWORDS:
  closes fixes resolves (auto-closes)
  part-of relates-to ref (links only)
```

## Support

- **GitHub CLI Docs:** https://cli.github.com/manual/
- **GitHub Issues Docs:** https://docs.github.com/issues
- **Project Issues:** https://github.com/slegroux/westside-la-events/issues
