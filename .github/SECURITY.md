# Security Policy

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability in the Westside LA Events Aggregator, please report it responsibly.

### How to Report

**Please DO NOT open a public GitHub issue for security vulnerabilities.**

Instead, please report security issues via one of these methods:

1. **Email** (Preferred): Send details to the project maintainers
   - Include "SECURITY" in the subject line
   - Provide a detailed description of the vulnerability
   - Include steps to reproduce if possible

2. **GitHub Security Advisory**: Use GitHub's private security advisory feature
   - Go to the repository's "Security" tab
   - Click "Report a vulnerability"

### What to Include

Please include as much information as possible:

- Type of vulnerability (e.g., SQL injection, XSS, authentication bypass)
- Full paths of source file(s) affected
- Location of the affected code (tag/branch/commit or direct URL)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the vulnerability
- Any potential mitigations you've identified

### Response Timeline

- **Initial Response**: Within 48 hours
- **Assessment**: Within 1 week
- **Fix Timeline**: Depends on severity
  - Critical: Immediate (within 24-48 hours)
  - High: Within 1 week
  - Medium: Within 2-4 weeks
  - Low: Best effort basis

### Disclosure Policy

- We will acknowledge receipt of your vulnerability report
- We will provide an estimated timeline for a fix
- We will notify you when the vulnerability is fixed
- We request that you do not publicly disclose the vulnerability until we've had a chance to address it
- We will credit you in the security advisory (unless you prefer to remain anonymous)

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

Only the latest release receives security updates.

## Security Best Practices

When contributing or deploying this project, please follow these security guidelines:

### For Contributors

1. **Never commit secrets**
   - API keys, passwords, tokens should be in `.env` (gitignored)
   - Use environment variables for sensitive data
   - Review commits before pushing

2. **Input validation**
   - Validate and sanitize all user inputs
   - Use parameterized queries (we use SQLAlchemy ORM)
   - Avoid string interpolation in SQL queries

3. **Web scraping safety**
   - Respect robots.txt
   - Implement rate limiting
   - Handle errors gracefully
   - Don't scrape authenticated content without permission

4. **Dependencies**
   - Keep dependencies up to date
   - Review dependency security advisories
   - Use `pip audit` or similar tools

5. **Code review**
   - All PRs require review
   - Look for common vulnerabilities (OWASP Top 10)
   - Test security-sensitive changes thoroughly

### For Deployers

1. **Environment configuration**
   - Never commit `.env` files
   - Use strong, unique API keys
   - Limit API key permissions to minimum required
   - Rotate keys periodically

2. **Database security**
   - Ensure SQLite file has proper permissions (600 or 640)
   - Regular backups
   - Keep database in secure location

3. **Web server security**
   - Use HTTPS in production
   - Set proper CORS policies
   - Implement rate limiting
   - Use a reverse proxy (nginx, Caddy)
   - Keep server software updated

4. **Monitoring**
   - Monitor logs for suspicious activity
   - Set up error alerting
   - Track failed requests

## Known Security Considerations

### Current Implementation

1. **API Authentication**: Currently none
   - The API is publicly accessible
   - No rate limiting implemented yet
   - Consider API keys for production deployments

2. **CORS**: Not configured
   - Default same-origin policy applies
   - Configure CORS if needed for cross-origin requests

3. **Input Sanitization**: Implemented
   - Full-text search uses parameterized queries
   - SQL injection vulnerability fixed (see [docs/SECURITY_FTS_FIX.md](../docs/SECURITY_FTS_FIX.md))

4. **External Content**: Third-party sources
   - Event data comes from external websites
   - Images loaded from external sources
   - Be aware of mixed content issues (HTTP/HTTPS)

### Planned Security Enhancements

- [ ] API rate limiting
- [ ] API authentication (API keys)
- [ ] CORS configuration
- [ ] Content Security Policy (CSP) headers
- [ ] Request size limits
- [ ] IP-based rate limiting
- [ ] Security headers (HSTS, X-Frame-Options, etc.)
- [ ] Input validation middleware
- [ ] Automated dependency vulnerability scanning

## Security-Related Documentation

- [SECURITY_FTS_FIX.md](../docs/SECURITY_FTS_FIX.md) - Full-text search SQL injection fix
- [SCRAPING_GUIDE.md](../docs/SCRAPING_GUIDE.md) - Ethical web scraping practices
- [SDD.md](../SDD.md) - Security considerations in architecture

## Third-Party Dependencies

We use various third-party libraries. Security vulnerabilities may exist in dependencies. We regularly:

- Monitor GitHub security advisories
- Update dependencies when security patches are available
- Review dependency permissions and scope

Key dependencies:
- FastHTML/Starlette (web framework)
- SQLAlchemy (database ORM)
- BeautifulSoup4 (HTML parsing)
- Playwright (browser automation)
- Requests (HTTP client)

## Responsible Disclosure Example

We appreciate security researchers who:
- Follow responsible disclosure practices
- Give us reasonable time to fix issues
- Don't exploit vulnerabilities maliciously
- Help us improve security for all users

### Hall of Fame

We will recognize security researchers who responsibly disclose vulnerabilities:

<!-- Security researchers who help us will be listed here -->

*No security vulnerabilities have been reported yet.*

---

## Questions?

If you have questions about this security policy, please open a GitHub issue with the label "security-question" (for non-sensitive questions) or contact the maintainers directly.

**Thank you for helping keep Westside LA Events Aggregator secure!** 🔒
