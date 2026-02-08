---
name: ship
description: Use when the user wants to commit, push, AND deploy to production. Also use when the user says "ship it", "deploy", or "ship to prod". For push-only (no deploy), use /push instead.
---

# /ship - Test, commit, track issues, push, and deploy

You are running the **ship** workflow. This is an automated pipeline that:
1. Runs tests to catch breakage
2. Stages and commits changes with proper issue references
3. Creates/updates/closes GitHub issues to match the work done
4. Pushes to remote
5. Deploys to production (this is what distinguishes `/ship` from `/push`)

## Important context
- This is a solo-dev project on `master` branch (no PRs needed)
- Use `conda run -n la` for all Python/test commands (NOT micromamba)
- Use `conda run -n la gh` for all GitHub CLI commands
- Skip E2E tests: `--ignore=tests/e2e`
- Pre-existing test failure `test_scraper_has_base_url[LATechEventsScraper]` can be ignored
- The user's GitHub is authenticated via `gh auth`

---

## Step 1: Preview - Show What Will Happen

Before doing anything, gather the full picture and present a summary to the user.

Run these commands (in parallel where possible):

1. `git status` and `git diff --stat` - uncommitted changes
2. `git log origin/master..HEAD --oneline` - unpushed commits
3. `conda run -n la gh issue list --state open --limit 50` - open issues for matching

Then present a preview like this:

```
## /ship Preview
**Uncommitted changes:** N files modified, N new files
  - src/scrapers/foo.py (modified)
  - src/web/app.py (modified)

**Unpushed commits:** N commits
  - abc1234 Previous commit message

**Matching issues:** #35 UX Improvements, #44 Prefetching (or "no matches - will create new")

**Plan:**
1. Run tests
2. Stage and commit with message: "<draft message>"
3. Update issues: #35 (comment), create new issue for <topic>
4. Push to origin/master
5. Deploy to Cloud Run
```

Wait for the user to confirm before proceeding. If the user says to adjust something (different commit message, skip a file, etc.), incorporate their feedback.

If there are no changes AND no unpushed commits, tell the user "Nothing to ship!" and stop.

---

## Step 2: Run Tests

Run the test suite. If tests fail (beyond known failures), STOP and report the failures. Do not commit broken code.

```
conda run -n la python -m pytest tests/ --ignore=tests/e2e -x -q --timeout=30
```

Known acceptable failures:
- `test_scraper_has_base_url[LATechEventsScraper]` (pre-existing)

If there are NEW failures, stop and ask the user whether to proceed or fix first.

---

## Step 3: Stage and Commit (if uncommitted changes)

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

Now analyze ALL unpushed commits (including the one you just created) and match them to GitHub issues.

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

## Step 6: Deploy to Production

After a successful push, deploy:

1. Sync the database: `conda run -n la bash scripts/sync_db_to_cloud.sh --force`
2. Deploy code: `conda run -n la bash scripts/deploy.sh`
3. Report the deployment status

If either step fails, report the error and suggest next steps.

---

## Output Summary

At the end, print a clear summary:

```
## Ship Summary
- Tests: passed/failed (N tests)
- Commit: <short-sha> <message>
- Issues created: #N, #N
- Issues updated: #N, #N
- Issues closed: #N, #N
- Pushed: master -> origin/master
- Deploy: [deployed / skipped]
```
