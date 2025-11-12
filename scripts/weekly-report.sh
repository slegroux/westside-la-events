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
