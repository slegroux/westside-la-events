# Issue Tracking Summary

Quick reference for ensuring features are properly tracked and closed.

## The Complete Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                     FEATURE LIFECYCLE                        │
└─────────────────────────────────────────────────────────────┘

1. PLANNING
   └─> Create issue with:
       • Clear title: [FEATURE] Add dark mode
       • Task list in description
       • Assign to milestone
       • Add labels (type, priority, area)

2. STARTING WORK
   └─> Branch name references issue
       • git checkout -b feature/dark-mode-#42
       • Mark issue as "In Progress" (if using Projects)

3. DURING DEVELOPMENT
   └─> Commits reference issue
       • git commit -m "Add dark mode toggle\n\nPart of #42"
       • Check off subtasks in issue as completed

4. CREATING PR
   └─> PR description closes issue
       • gh pr create --title "..." --body "Closes #42"
       • PR automatically labeled by GitHub Action

5. AFTER MERGE
   └─> Verify and document
       • Issue automatically closes
       • GitHub Action comments with milestone progress
       • Update PLAN.md checkboxes
       • Update documentation

┌─────────────────────────────────────────────────────────────┐
│                     DAILY WORKFLOW                           │
└─────────────────────────────────────────────────────────────┘

MORNING:
  ./scripts/daily-standup.sh
  ├─> View assigned tasks
  ├─> Check high priority issues
  └─> Review milestone progress

DURING DAY:
  • Commit with issue references
  • Update task lists in issues
  • Create PRs with "Closes #N"

EVENING:
  • Review PRs
  • Merge completed work
  • Verify issues auto-closed

WEEKLY:
  ./scripts/weekly-report.sh
  ├─> Issues closed this week
  ├─> Issues created this week
  └─> Open high priority issues

┌─────────────────────────────────────────────────────────────┐
│                  AUTOMATION IN PLACE                         │
└─────────────────────────────────────────────────────────────┘

✅ Git Hook: prepare-commit-msg
   • Warns if commit lacks issue reference
   • Located: .git/hooks/prepare-commit-msg

✅ GitHub Action: issue-tracking.yml
   • Comments milestone progress when issues close
   • Checks for labels on new issues
   • Auto-labels PRs by changed files
   • Links related issues

✅ Scripts: scripts/
   • daily-standup.sh - Daily report
   • check-milestone-progress.sh - Milestone status
   • weekly-report.sh - Weekly summary
   • feature-done-checklist.sh - Completion checklist

┌─────────────────────────────────────────────────────────────┐
│                  CLOSING KEYWORDS                            │
└─────────────────────────────────────────────────────────────┘

Use these in commit messages or PR descriptions:

CLOSES ISSUE (when merged to main):
  • closes #42
  • fixes #42
  • resolves #42
  • close #42
  • fix #42
  • resolve #42

LINKS BUT DOESN'T CLOSE:
  • part of #42
  • relates to #42
  • see #42
  • ref #42

MULTIPLE ISSUES:
  • Closes #42, closes #43, closes #44

┌─────────────────────────────────────────────────────────────┐
│                  MILESTONE STRUCTURE                         │
└─────────────────────────────────────────────────────────────┘

📌 Phase 1: MVP (Due: Jan 31, 2025)
   Core: Database, 3 scrapers, basic UI, maps, search
   Issues: 6 open

📌 Phase 2: Enhancement (Due: Feb 14, 2025)
   More scrapers, scheduling, advanced filters
   Issues: 5 open

📌 Phase 3: Polish (Due: Feb 28, 2025)
   Deduplication, performance, UX, deployment
   Issues: 5 open

📌 Testing & Quality (Due: Mar 14, 2025)
   Comprehensive testing suite
   Issues: 1 open

📌 Future Enhancements (No due date)
   Post-MVP features
   Issues: 4 open

┌─────────────────────────────────────────────────────────────┐
│                  QUICK COMMANDS                              │
└─────────────────────────────────────────────────────────────┘

# Daily workflow
./scripts/daily-standup.sh
gh issue list --assignee @me

# View milestone progress
./scripts/check-milestone-progress.sh
gh issue list --milestone "Phase 1: MVP"

# Before completing feature
./scripts/feature-done-checklist.sh 42

# Create issue
gh issue create --title "[FEATURE] Add dark mode" \
  --body "..." \
  --milestone "Phase 3: Polish" \
  --label "type: feature,priority: medium,area: frontend"

# Create PR that closes issue
gh pr create --title "Add dark mode" \
  --body "Closes #42"

# Close issue manually
gh issue close 42 --comment "Implemented and tested"

# View specific issue
gh issue view 42

# Search issues
gh issue list --search "dark mode"
gh issue list --label "priority: high"

┌─────────────────────────────────────────────────────────────┐
│                  CHECKLIST FOR CLOSING                       │
└─────────────────────────────────────────────────────────────┘

Before closing any feature issue:

Pre-merge:
  ☐ All subtasks completed
  ☐ Unit tests written and passing
  ☐ Integration tests written and passing
  ☐ Manual testing completed
  ☐ Code reviewed
  ☐ Documentation updated
  ☐ PR created with "Closes #N"

Post-merge:
  ☐ Verify issue auto-closed
  ☐ Verify milestone progress updated
  ☐ Update PLAN.md checkboxes
  ☐ Announce/demo feature (if applicable)

┌─────────────────────────────────────────────────────────────┐
│                  TROUBLESHOOTING                             │
└─────────────────────────────────────────────────────────────┘

❌ Issue didn't auto-close after PR merge?
   → Check if "Closes #N" was in PR description (not just commits)
   → Manually close: gh issue close N --comment "Closed by PR #M"

❌ Forgot to reference issue in commits?
   → Amend last commit: git commit --amend
   → Or reference in PR description: "Closes #N"

❌ Need to move issue to different milestone?
   → gh issue edit N --milestone "Phase 2: Enhancement"

❌ Issue labeled wrong?
   → gh issue edit N --add-label "priority: high"
   → gh issue edit N --remove-label "priority: low"

┌─────────────────────────────────────────────────────────────┐
│                  FURTHER READING                             │
└─────────────────────────────────────────────────────────────┘

📖 docs/GITHUB_WORKFLOW.md
   Complete workflow guide with examples

📖 scripts/README.md
   Automation scripts documentation

📖 .github/ISSUE_TEMPLATE/
   Issue templates for consistency

📖 PLAN.md
   Development roadmap with task checkboxes
