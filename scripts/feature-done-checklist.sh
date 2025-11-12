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
