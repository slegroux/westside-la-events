---
name: push
description: Use when the user wants to commit and push work to GitHub without deploying. Also use when the user says "push this", "commit and push", "update git", or "sync to github".
---

# /push - Test, commit, track issues, and push

You are running the **push** workflow. This commits and pushes code to GitHub with proper issue tracking, but does NOT deploy to production. Use `/ship` for the full pipeline including deploy.

## Important context
- This is a solo-dev project on `master` branch (no PRs needed)
- Use `conda run -n la` for all Python/test commands (NOT micromamba)
- Use `conda run -n la gh` for all GitHub CLI commands
- Skip E2E tests: `--ignore=tests/e2e`
- Pre-existing test failure `test_scraper_has_base_url[LATechEventsScraper]` can be ignored
- The user's GitHub is authenticated via `gh auth`

---

## Step 1: Run Tests

Run the test suite first. If tests fail (beyond known failures), STOP and report the failures. Do not commit broken code.

```
conda run -n la python -m pytest tests/ --ignore=tests/e2e -x -q --timeout=30
```

Known acceptable failures:
- `test_scraper_has_base_url[LATechEventsScraper]` (pre-existing)

If there are NEW failures, stop and ask the user whether to proceed or fix first.

---

## Step 2: Analyze Changes

Gather the full picture of what needs to be pushed:

1. **Uncommitted changes**: Run `git status` and `git diff --stat` to see dirty working tree
2. **Unpushed commits**: Run `git log origin/master..HEAD --oneline` to see commits not yet on remote
3. **Recent commit messages**: Run `git log --oneline -10` for style reference

If there are no changes AND no unpushed commits, tell the user "Nothing to push!" and stop.

---

## Step 3: Stage and Commit (if dirty working tree)

If there are uncommitted changes:

1. Review the diff carefully to understand what was done
2. **Never stage files that look like secrets** (.env, credentials, tokens). Warn the user if you see any.
3. **Be selective** - use `git add <specific files>` not `git add -A`
4. Write a commit message that:
   - Summarizes the "why" in 1-2 sentences
   - References relevant GitHub issues with `#N` syntax
   - Uses `Closes #N` for fully completed issues, `Partial #N` for in-progress
   - Ends with `Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`
5. Commit using a HEREDOC for the message

---

## Step 4: Match Work to GitHub Issues

Analyze ALL unpushed commits (including the one you just created) and match them to GitHub issues.

1. **List open issues**: `conda run -n la gh issue list --state open --limit 50`
2. **List milestones**: `conda run -n la gh api repos/{owner}/{repo}/milestones --jq '.[] | "\(.number) \(.state) \(.title)"'`

For each piece of work in the unpushed commits, determine:

### A. Existing issues that got progress
- Add a comment with specific details of what was done
- If fully complete, close the issue with `conda run -n la gh issue close N --comment "Completed in <commit-sha>."`

### B. Work that doesn't match any existing issue
Create new issues with:
- Clear title (imperative mood, under 70 chars)
- Appropriate labels from: `bug`, `enhancement`, `area: frontend`, `area: scrapers`, `area: database`, `area: maps`, `area: search`, `area: performance`, `design`, `type: feature`, `type: enhancement`, `priority: high/medium/low`, `testing`, `devops`
- Appropriate milestone from: `Phase 2: Enhancement`, `Phase 3: Polish`, `Testing & Quality`, `Future Enhancements`
- Body with: summary, what's done (checked items), what remains (unchecked items)
- If the work is already complete, create the issue AND immediately close it (for tracking history)

### C. Stale issues
If you notice open issues that seem fully addressed by the codebase, flag them to the user and suggest closing.

---

## Step 5: Push

Push to remote:
```
git push
```

If push fails (e.g., remote has new commits), tell the user and suggest `git pull --rebase`.

---

## Output Summary

At the end, print a clear summary:

```
## Push Summary
- Tests: passed/failed (N tests)
- Commit: <short-sha> <message>
- Issues created: #N, #N
- Issues updated: #N, #N
- Issues closed: #N, #N
- Pushed: master -> origin/master
```
