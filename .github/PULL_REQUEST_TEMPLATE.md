# Pull Request

## Description

<!-- Brief description of what this PR does -->

## Type of Change

<!-- Check all that apply -->

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] New scraper (adds event source)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Code refactoring
- [ ] Performance improvement
- [ ] Test coverage improvement

## Related Issues

<!-- Link to related issues using #issue_number -->

Closes #
Related to #

## Changes Made

<!-- Detailed list of changes -->

-
-
-

## Testing

<!-- Describe how you tested these changes -->

### Test Environment
- [ ] Tested locally with micromamba environment
- [ ] All existing tests pass
- [ ] Added new tests for new functionality
- [ ] Manual testing completed

### Test Commands Run
```bash
# Add the commands you ran to test
env -u PYTHONPATH -u AMENT_PREFIX_PATH -u ROS_DISTRO PYTHONNOUSERSITE=1 micromamba run -n la python -m pytest tests/ -v
```

### Test Results
<!-- Describe test results, include screenshots if relevant -->

## Scraper-Specific (if applicable)

<!-- Fill this section if adding or modifying a scraper -->

- [ ] Scraper inherits from `BaseScraper`
- [ ] Scraper handles errors gracefully
- [ ] Events have required fields (title, date, venue, url)
- [ ] Geocoding is implemented for addresses
- [ ] Geographic filtering validates events are in Westside LA
- [ ] Scraper respects rate limits and robots.txt
- [ ] Added scraper test in `tests/scrapers/`
- [ ] Added scraper configuration in `config.py`
- [ ] Registered scraper in `run_scrapers.py`

**Scraper Details:**
- Source name:
- Base URL:
- Scraping method: [ ] Static HTML [ ] API [ ] JavaScript-rendered (Playwright)
- Average events per scrape:

## Documentation

- [ ] Updated relevant documentation
- [ ] Added docstrings to new functions/classes
- [ ] Updated [CHANGELOG.md](../CHANGELOG.md)
- [ ] Added comments for complex logic

## Code Quality

- [ ] Code follows project style guidelines (PEP 8)
- [ ] Used type hints for function signatures
- [ ] No unnecessary print statements or debug code
- [ ] Removed commented-out code
- [ ] Variable/function names are descriptive
- [ ] No hardcoded credentials or sensitive data

## Pre-Submission Checklist

- [ ] Branch is up to date with `master`
- [ ] All tests pass locally
- [ ] Code has been reviewed for security issues
- [ ] No merge conflicts
- [ ] Commit messages are clear and descriptive
- [ ] PR title clearly describes the change

## Screenshots (if applicable)

<!-- Add screenshots for UI changes -->

## Additional Notes

<!-- Any additional information reviewers should know -->

---

## For Reviewers

### Review Focus Areas

<!-- Highlight specific areas that need careful review -->

-
-

### Questions for Reviewers

<!-- Any specific questions for reviewers -->

-

---

**Thank you for contributing to Westside LA Events Aggregator!** 🎉
