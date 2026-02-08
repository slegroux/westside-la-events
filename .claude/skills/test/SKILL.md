---
name: test
description: Use when the user wants to run the test suite. Also use when the user says "run tests", "test it", "check tests", or "make sure tests pass".
---

# /test - Run the test suite

You are running the **test** workflow. This runs the project's test suite and reports results. It does NOT commit, push, or deploy anything.

## Important context
- Use `conda run -n la` for all Python commands (NOT micromamba)
- Skip E2E tests: `--ignore=tests/e2e`
- Pre-existing test failure `test_scraper_has_base_url[LATechEventsScraper]` can be ignored

---

## Step 1: Run Tests

```
conda run -n la python -m pytest tests/ --ignore=tests/e2e -x -q --timeout=30
```

---

## Step 2: Report Results

Present a clear summary:

```
## Test Results
- Status: PASSED / FAILED
- Tests: N passed, N failed, N skipped
- Known failures ignored: test_scraper_has_base_url[LATechEventsScraper]
```

If there are NEW failures (beyond the known one), list each failure with:
- Test name
- Brief description of the error
- Suggested fix if obvious

If all tests pass, tell the user they're good to `/push` or `/ship`.
