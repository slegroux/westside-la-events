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

## Step 1: Preview - Show What Will Happen

Before doing anything, gather the full picture and present a summary to the user.

Run these commands (in parallel where possible):

1. `git status` and `git diff --stat` - uncommitted changes
2. `git log origin/master..HEAD --oneline` - unpushed commits
3. `conda run -n la gh issue list --state open --limit 50` - open issues for matching
4. `conda run -n la gh api repos/{owner}/{repo}/milestones --jq '.[] | "\(.number) \(.state) \(.title)"'` - milestones for categorization

Then present a preview as a **table mapping each changed file to its matching issue(s)**:

```
## /push Preview

| File | Change | Issue(s) | Milestone |
|------|--------|----------|-----------|
| `src/scrapers/foo.py` | Fix prefetch cache bug | #44 Prefetching | Phase 2 |
| `src/web/app.py` | Add scroll-to-top, footer redesign | #42 Design system, #35 UX | Phase 2 |
| `static/css/style.css` | Hero photo, footer styles | #42 Design system | Phase 2 |
| `data/events.db` | Updated event data | skip | — |
| `tests/test_new.py` *(new)* | New scraper tests | #37 Testing | Testing & Quality |

**Unpushed commits:** N commits (or "none")
  - abc1234 Previous commit message

**Plan:**
1. Run tests
2. Stage and commit: "<draft message>"
3. Update issues: #35 (comment), close #44, create new for <topic>
4. Push to origin/master
```

Table conventions:
- Group related files into one row if they share the same logical change and issue
- Mark new files with *(new)* and deleted files with *(deleted)* after the filename
- Use "skip" in the Issue column for data files (`.db`, cache JSON) that don't map to issues
- Use "new issue?" in the Issue column for work that doesn't match any open issue
- Use "—" in the Milestone column for rows that don't apply (skipped files, data-only changes)

Wait for the user to confirm before proceeding. If the user says to adjust something (different commit message, skip a file, etc.), incorporate their feedback.

If there are no changes AND no unpushed commits, tell the user "Nothing to push!" and stop.

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

Analyze ALL unpushed commits (including the one you just created) and match them to GitHub issues.

1. **List open issues** (already fetched in Step 1)
2. **List milestones** (already fetched in Step 1)

For each piece of work in the unpushed commits, determine:

### A. Existing issues that got progress
- **Update checkboxes**: Fetch the issue body with `conda run -n la gh issue view N --json body --jq .body`. If it contains unchecked items (`- [ ]`) that are now done, edit the body to check them off (`- [x]`) using `conda run -n la gh issue edit N --body "..."`. Use a HEREDOC for the body to preserve formatting.
- **Add a comment** with specific details of what was done and which commit(s) addressed it
- If ALL checkboxes are now checked and the issue is fully complete, close it with `conda run -n la gh issue close N --comment "Completed in <commit-sha>."`

### B. Work that doesn't match any existing issue
Create new issues with:
- Clear title (imperative mood, under 70 chars)
- Appropriate labels from: `bug`, `enhancement`, `area: frontend`, `area: scrapers`, `area: database`, `area: maps`, `area: search`, `area: performance`, `design`, `type: feature`, `type: enhancement`, `priority: high/medium/low`, `testing`, `devops`
- Appropriate milestone from: `Core Platform`, `Scrapers & Filters`, `Design & Performance`, `Testing & Quality`, `User Features & Integrations`
- **Body must use checkbox format**:
  ```
  ## Summary
  Brief description of the work.

  ## Tasks
  - [x] Completed item from this commit
  - [x] Another completed item
  - [ ] Remaining work (if any)

  ## Acceptance Criteria
  - Criterion 1
  - Criterion 2
  ```
- If the work is already complete (all boxes checked), create the issue AND immediately close it (for tracking history)

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
