#!/bin/bash
# Daily standup report - what you need to know today

echo "======================================"
echo "    Daily Development Standup"
echo "======================================"
echo
echo "📅 $(date '+%A, %B %d, %Y')"
echo

echo "🎯 Your Tasks Today:"
echo "-------------------"
gh issue list --assignee @me --json number,title,milestone --jq '.[] | "  #\(.number) - \(.title) [\(.milestone.title // "No milestone")]"'
echo

echo "🔥 High Priority Issues:"
echo "------------------------"
gh issue list --label "priority: high" --limit 5 --json number,title,assignees --jq '.[] | "  #\(.number) - \(.title) [Assigned: \(if .assignees | length > 0 then .assignees[0].login else "Unassigned" end)]"'
echo

echo "✅ Recently Closed (Last 3 days):"
echo "--------------------------------"
DAYS_AGO=$(date -d '3 days ago' +%Y-%m-%d)
gh issue list --state closed --search "closed:>=$DAYS_AGO" --limit 5 --json number,title,closedAt --jq '.[] | "  #\(.number) - \(.title)"'
echo

echo "📊 Milestone Progress:"
echo "---------------------"
gh api repos/:owner/:repo/milestones | python -m json.tool | \
  jq -r '.[] | select(.state == "open") | "  \(.title): \(if (.open_issues + .closed_issues) > 0 then ((.closed_issues * 100 / (.open_issues + .closed_issues)) | floor) else 0 end)% complete"'
echo

echo "💡 Quick Actions:"
echo "----------------"
echo "  gh issue list --assignee @me    # View your assigned issues"
echo "  gh issue view <number>          # View specific issue"
echo "  gh pr list --author @me         # View your PRs"
echo "  ./scripts/check-milestone-progress.sh  # Full milestone report"
echo
