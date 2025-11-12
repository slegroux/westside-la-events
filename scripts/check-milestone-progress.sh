#!/bin/bash
# Check milestone progress

echo "=== Milestone Progress Report ==="
echo

gh api repos/:owner/:repo/milestones | python -m json.tool | \
  jq -r '.[] | "\(.title)\n  Open: \(.open_issues)\n  Closed: \(.closed_issues)\n  Progress: \(if (.open_issues + .closed_issues) > 0 then ((.closed_issues * 100 / (.open_issues + .closed_issues)) | floor) else 0 end)%\n"'
