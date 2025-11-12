# GitHub Workflow Guide

## Overview

This guide explains how to track GitHub milestones, issues, and subtasks, and ensure proper closure when features are implemented in the Westside LA Events Aggregator project.

## Current Milestone Structure

We have 5 milestones that map to our development phases:

1. **Phase 1: MVP** (Due: Jan 31, 2025)
   - Core functionality: database, 3 scrapers, basic UI, maps, and search
   - 6 open issues

2. **Phase 2: Enhancement** (Due: Feb 14, 2025)
   - More scrapers, scheduling, advanced filters, map improvements
   - 5 open issues

3. **Phase 3: Polish** (Due: Feb 28, 2025)
   - Deduplication, detail pages, performance, UX, deployment
   - 5 open issues

4. **Testing & Quality** (Due: Mar 14, 2025)
   - Comprehensive testing suite
   - 1 open issue

5. **Future Enhancements** (No due date)
   - Post-MVP features
   - 4 open issues

## Issue Management Workflow

### 1. Linking Issues to Milestones

When creating or updating issues, always assign them to the appropriate milestone:

```bash
# Assign issue to milestone
gh issue edit <issue-number> --milestone "Phase 1: MVP"

# Example: Assign issue #21 (Database Setup) to Phase 1
gh issue edit 21 --milestone "Phase 1: MVP"
```

### 2. Creating Subtasks with Task Lists

GitHub supports task lists in issue descriptions. Use them for breaking down complex features:

**Example Issue Description:**
```markdown
## Description
Implement event deduplication system to merge duplicate events from different sources.

## Tasks
- [ ] Design fuzzy matching algorithm (title + date + location)
- [ ] Implement similarity scoring function
- [ ] Create merge logic for duplicate events
- [ ] Track all source URLs for merged events
- [ ] Add database migration for new fields
- [ ] Write unit tests
- [ ] Write integration tests
- [ ] Update documentation

## Acceptance Criteria
- Events with 85%+ similarity are marked as duplicates
- Merged events retain all source URLs
- No false positives in manual testing
```

GitHub will show "0 of 8 tasks complete" on the issue list view.

### 3. Using Issue References in Commits

Link commits to issues using keywords in commit messages:

```bash
# These keywords will automatically close issues when merged to main:
# closes, fixes, resolves (case-insensitive)

git commit -m "Add deduplication algorithm

- Implement fuzzy string matching
- Add similarity scoring
- Create merge logic

Closes #32"
```

**Supported keywords:**
- `closes #32` or `fixes #32` - closes the issue
- `relates to #32` or `see #32` - links but doesn't close
- `part of #32` - indicates partial work

### 4. Closing Issues via Pull Requests

Link PRs to issues in the PR description:

```bash
gh pr create --title "Implement event deduplication" --body "$(cat <<'EOF'
## Summary
- Implements fuzzy matching for duplicate detection
- Compares title similarity, date, and location
- Merges duplicate events from different sources

## Closes
- Closes #32

## Test Plan
- [x] Unit tests for similarity scoring
- [x] Integration tests for merge logic
- [x] Manual testing with known duplicates

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

When the PR is merged, issue #32 will automatically close.

### 5. Tracking Feature Implementation Progress

#### Daily Progress Check
```bash
# View milestone progress
gh api repos/:owner/:repo/milestones | \
  python -m json.tool | \
  grep -E '"title"|"open_issues"|"closed_issues"'

# View issues by milestone
gh issue list --milestone "Phase 1: MVP"

# View issues by label
gh issue list --label "priority: high"
```

#### Weekly Review
```bash
# Issues closed this week
gh issue list --state closed --search "closed:>=$(date -d '7 days ago' +%Y-%m-%d)"

# Issues created this week
gh issue list --search "created:>=$(date -d '7 days ago' +%Y-%m-%d)"
```

### 6. Automated Issue Closure Workflow

Create a git alias for feature completion:

```bash
# Add to ~/.gitconfig
[alias]
    feature-done = "!f() { \
        issue=$1; \
        git add -A && \
        git commit -m \"$(git branch --show-current | sed 's/-/ /g')\n\nCloses #$issue\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)\n\nCo-Authored-By: Claude <noreply@anthropic.com>\" && \
        git push; \
    }; f"
```

Usage:
```bash
# On feature branch, when done:
git feature-done 32
# Commits, pushes, and references issue #32
```

### 7. Issue Templates

Create issue templates to ensure consistency. Create `.github/ISSUE_TEMPLATE/`:

**feature.md:**
```markdown
---
name: Feature Request
about: Propose a new feature
title: '[FEATURE] '
labels: 'type: feature'
assignees: ''
---

## Description
Brief description of the feature

## User Story
As a [user type], I want [goal] so that [reason]

## Tasks
- [ ] Task 1
- [ ] Task 2
- [ ] Write tests
- [ ] Update documentation

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Related Issues
- Relates to #
```

**bug.md:**
```markdown
---
name: Bug Report
about: Report a bug
title: '[BUG] '
labels: 'type: bug'
assignees: ''
---

## Description
Brief description of the bug

## Steps to Reproduce
1. Step 1
2. Step 2
3. Step 3

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- Python version:
- Browser (if applicable):
- OS:

## Related Issues
- Relates to #
```

### 8. Bulk Operations

#### Assign Multiple Issues to Milestone
```bash
# Assign issues 21-26 to Phase 1
for i in {21..26}; do
  gh issue edit $i --milestone "Phase 1: MVP"
done
```

#### Update Labels in Bulk
```bash
# Add "priority: high" to issues 21, 23, 24, 25, 26
for i in 21 23 24 25 26; do
  gh issue edit $i --add-label "priority: high"
done
```

#### Close Completed Issues
```bash
# Close issue with comment
gh issue close 21 --comment "Completed: Database schema implemented and tested"
```

### 9. GitHub Projects (Kanban Board)

For visual tracking, create a GitHub Project board:

```bash
# Create a project
gh project create --owner @me --title "LA Events Development" --description "Track all development tasks"

# Link issues to project (requires project ID from above)
gh issue edit 21 --add-project "LA Events Development"
```

**Recommended columns:**
- Backlog
- To Do (this sprint/week)
- In Progress
- In Review (PR open)
- Done

### 10. Workflow Integration with Development

#### Before Starting Work
1. Check milestone and issue assignments
2. Create a feature branch named after the issue
3. Move issue to "In Progress" (if using Projects)

```bash
# Check assigned issues
gh issue list --assignee @me

# Create feature branch
git checkout -b feature/deduplication-#32
```

#### During Development
1. Make small, focused commits
2. Reference the issue number in commits
3. Update task list checkboxes in the issue as you complete subtasks

```bash
# Regular commits
git commit -m "Add similarity scoring function

Part of #32"

# Update issue description (manually on GitHub or via API)
```

#### After Completing Feature
1. Ensure all subtasks are checked
2. Create PR with "Closes #32" in description
3. Request review
4. After merge, verify issue auto-closed
5. Update PLAN.md checkboxes if applicable

```bash
# Create PR
gh pr create --title "Implement event deduplication" \
  --body "Closes #32" \
  --milestone "Phase 2: Enhancement"

# After merge, verify closure
gh issue view 32
# Should show: STATE: CLOSED
```

## Best Practices

### 1. Issue Naming Convention
- **Feature:** `[FEATURE] Add event deduplication system`
- **Bug:** `[BUG] Map markers not clustering correctly`
- **Enhancement:** `[ENHANCEMENT] Improve geocoding accuracy`
- **Test:** `[TEST] Add scraper integration tests`

### 2. Label Strategy
Use consistent labels:
- **Type:** `type: feature`, `type: bug`, `type: enhancement`, `type: documentation`
- **Priority:** `priority: high`, `priority: medium`, `priority: low`
- **Area:** `area: frontend`, `area: backend`, `area: scrapers`, `area: database`, `area: maps`, `area: search`
- **Status:** `status: blocked`, `status: needs-discussion`, `status: ready`
- **Testing:** `testing`, `needs-tests`

### 3. Milestone Management
- Assign every issue to a milestone (or "Future Enhancements")
- Review milestone progress weekly
- Adjust due dates if needed
- Close milestones when all issues are resolved

### 4. Documentation Updates
When closing feature issues, ensure:
- [ ] PLAN.md checkboxes updated
- [ ] README.md updated if user-facing
- [ ] CLAUDE.md updated if architecture changed
- [ ] Code comments and docstrings added

### 5. Testing Requirements
Before closing feature issues:
- [ ] Unit tests written and passing
- [ ] Integration tests written and passing
- [ ] Manual testing completed
- [ ] Edge cases tested

## Automation Scripts

### Script 1: Check Milestone Progress

Create `scripts/check-milestone-progress.sh`:

```bash
#!/bin/bash
# Check milestone progress

echo "=== Milestone Progress Report ==="
echo

gh api repos/:owner/:repo/milestones | python -m json.tool | \
  jq -r '.[] | "\(.title)\n  Open: \(.open_issues)\n  Closed: \(.closed_issues)\n  Progress: \((.closed_issues * 100 / (.open_issues + .closed_issues) | floor))%\n"'
```

### Script 2: Weekly Issue Report

Create `scripts/weekly-report.sh`:

```bash
#!/bin/bash
# Generate weekly issue report

WEEK_AGO=$(date -d '7 days ago' +%Y-%m-%d)

echo "=== Weekly Issue Report ==="
echo
echo "Issues Closed This Week:"
gh issue list --state closed --search "closed:>=$WEEK_AGO" --json number,title,closedAt --jq '.[] | "  #\(.number) - \(.title)"'
echo
echo "Issues Created This Week:"
gh issue list --search "created:>=$WEEK_AGO" --json number,title,createdAt --jq '.[] | "  #\(.number) - \(.title)"'
echo
echo "Open High Priority Issues:"
gh issue list --label "priority: high" --json number,title --jq '.[] | "  #\(.number) - \(.title)"'
```

### Script 3: Feature Completion Checklist

Create `scripts/feature-done-checklist.sh`:

```bash
#!/bin/bash
# Feature completion checklist

ISSUE=$1
if [ -z "$ISSUE" ]; then
  echo "Usage: ./feature-done-checklist.sh <issue-number>"
  exit 1
fi

echo "Feature Completion Checklist for Issue #$ISSUE"
echo "================================================"
echo
echo "Pre-merge Checklist:"
echo "  [ ] All subtasks in issue completed"
echo "  [ ] Unit tests written and passing"
echo "  [ ] Integration tests written and passing"
echo "  [ ] Manual testing completed"
echo "  [ ] Code reviewed"
echo "  [ ] Documentation updated (README, PLAN.md, etc.)"
echo "  [ ] No console errors or warnings"
echo "  [ ] PR created with 'Closes #$ISSUE'"
echo
echo "Post-merge Checklist:"
echo "  [ ] Verify issue auto-closed"
echo "  [ ] Update PLAN.md checkboxes"
echo "  [ ] Announce in team chat (if applicable)"
echo "  [ ] Deploy to staging/production"
echo
echo "Run this after merge:"
echo "  gh issue view $ISSUE"
```

## Quick Reference Commands

```bash
# List all milestones with progress
gh api repos/:owner/:repo/milestones | python -m json.tool | jq -r '.[] | "\(.title): \(.open_issues) open, \(.closed_issues) closed"'

# List issues by milestone
gh issue list --milestone "Phase 1: MVP"

# List high priority issues
gh issue list --label "priority: high"

# View specific issue
gh issue view 32

# Close issue with comment
gh issue close 32 --comment "Implemented and tested"

# Reopen issue
gh issue reopen 32

# Update issue milestone
gh issue edit 32 --milestone "Phase 2: Enhancement"

# Add label to issue
gh issue edit 32 --add-label "priority: high"

# Create issue with milestone and labels
gh issue create --title "Add dark mode" \
  --body "Implement dark mode toggle" \
  --milestone "Phase 3: Polish" \
  --label "type: feature,priority: medium,area: frontend"

# Search issues
gh issue list --search "deduplication"
gh issue list --search "is:open label:bug"
gh issue list --search "is:closed milestone:\"Phase 1: MVP\""
```

## Integration with PLAN.md

Keep [PLAN.md](../PLAN.md) as the source of truth for task checklists. When checking off items in PLAN.md:

1. Close corresponding GitHub issue
2. Add comment with commit SHA or PR link
3. Update milestone progress

Example workflow:
```bash
# 1. Complete task in code
# 2. Update PLAN.md checkbox
# 3. Commit with issue reference
git add PLAN.md src/
git commit -m "Implement geocoding service

- Add Google Geocoding API client
- Implement address to lat/lng conversion
- Add caching for repeated API calls

Closes #23"

# 4. Push and create PR
git push
gh pr create --title "Implement geocoding service" --body "Closes #23"
```

## Monitoring and Alerts

Set up GitHub notifications for:
- Issues assigned to you
- Mentions in issues/PRs
- PR reviews requested
- Milestone due dates approaching

Configure in: https://github.com/settings/notifications

## Summary

**Daily:**
- Check assigned issues: `gh issue list --assignee @me`
- Update task lists in issues as you work
- Reference issues in commits

**Weekly:**
- Review milestone progress
- Close completed issues
- Update PLAN.md
- Triage new issues

**Per Feature:**
- Start: Create issue → assign milestone → create branch
- During: Make commits referencing issue
- Complete: Create PR with "Closes #N" → merge → verify closure
