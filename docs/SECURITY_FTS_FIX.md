# FTS5 Query Sanitization Security Fix

## Vulnerability Description

**Location**: [src/data/database.py:231](../src/data/database.py#L231)

**Issue**: Raw user input was being passed directly into SQLite FTS5 MATCH queries without sanitization, which could cause syntax errors or application crashes when users entered special characters or FTS operators.

### Attack Vector

FTS5 (Full-Text Search 5) has special syntax including:
- Quotes (`"`, `'`) for phrase searches
- Boolean operators (`AND`, `OR`, `NOT`, `NEAR`)
- Wildcards (`*`)
- Parentheses for grouping
- Special prefixes (`^`, `+`, `-`)

If a user enters a query like:
- `test"` (unmatched quote)
- `query AND` (incomplete operator)
- `(((` (unmatched parentheses)
- `*` (standalone wildcard)

These would trigger FTS syntax errors and crash the search endpoint.

### Impact

- **Availability**: Search functionality would fail with cryptic error messages
- **User Experience**: Poor error handling leads to broken functionality
- **Potential DoS**: Malicious users could repeatedly trigger errors

## Fix Implementation

### Solution: Query Sanitization Function

Added `sanitize_fts_query()` function that:
1. Escapes double quotes by doubling them (FTS5 syntax: `"` → `""`)
2. Wraps the entire query in double quotes to treat it as a phrase search
3. This neutralizes all special operators and treats them as literal text

```python
def sanitize_fts_query(query: str) -> str:
    """
    Sanitize user input for FTS5 MATCH queries to prevent syntax errors.

    Escapes quotes and wraps query in quotes to treat as phrase search,
    preventing special operators from being interpreted.
    """
    if not query or not query.strip():
        return '""'

    query = query.strip()
    query = query.replace('"', '""')  # Escape quotes
    return f'"{query}"'  # Wrap in quotes
```

### Changes Made

1. **[src/data/database.py](../src/data/database.py)**:
   - Added `sanitize_fts_query()` function
   - Modified `search_events()` method to sanitize query input before passing to FTS MATCH

2. **[tests/unit/test_database.py](../tests/unit/test_database.py)**:
   - Added comprehensive test class `TestFTSSanitization`
   - Tests for normal queries, special characters, operators, and malicious inputs
   - Verified that sanitization doesn't break functionality

## Testing

### Security Test Cases

The fix was tested against the following malicious queries:
- `test"` - Unmatched quote
- `"broken` - Unmatched opening quote
- `query AND` - Incomplete AND operator
- `test OR` - Incomplete OR operator
- `(((` - Unmatched parentheses
- `NOT` - Standalone NOT operator
- `*` - Wildcard alone
- `test AND (broken` - Mixed operators and unmatched parens
- `"test" OR "broken` - Mixed valid and invalid syntax

All queries now execute without errors.

### Test Coverage

Run tests with:
```bash
# Unit tests
unset PYTHONPATH && PYTHONNOUSERSITE=1 micromamba run -n la pytest tests/unit/test_database.py::TestFTSSanitization -v

# Demonstration script
micromamba run -n la python test_fts_security.py
```

**Results**: All 9 security tests pass, plus all existing database tests continue to pass (26 total).

## Trade-offs

### Limitations of Phrase Search Approach

By wrapping queries in quotes, we sacrifice some FTS5 features:
- Users cannot use boolean operators (AND, OR, NOT)
- Users cannot use wildcards (`*`)
- Users cannot use proximity search (NEAR)

### Alternative Considered: Token-Based Sanitization

An alternative approach would be to parse and validate FTS operators, allowing legitimate use while blocking malicious input. This would:
- Allow users to use AND/OR/NOT operators
- Enable wildcard searches
- Provide more powerful search capabilities

However, this approach:
- Is more complex to implement correctly
- Has higher risk of bypass vulnerabilities
- Requires maintaining a parser for FTS5 syntax

### Recommendation

For this application (event search), **phrase search is sufficient**:
- Most users search with simple keywords or phrases
- The application doesn't require advanced boolean search
- Security and reliability are prioritized over advanced features
- Results are good enough for typical use cases

If advanced search is needed in the future, consider:
1. Implementing a safe query parser
2. Using a separate "advanced search" mode with validation
3. Providing a query builder UI instead of raw text input

## Verification

To verify the fix is working:

1. Start the web application:
   ```bash
   micromamba run uvicorn src.web.app:app --host 127.0.0.1 --port 8000 --reload
   ```

2. Try searching with special characters:
   - `music"`
   - `art AND`
   - `test*`

3. Verify that searches complete without errors (even if no results)

## References

- [SQLite FTS5 Documentation](https://www.sqlite.org/fts5.html)
- [FTS5 Query Syntax](https://www.sqlite.org/fts5.html#full_text_query_syntax)
- [OWASP Input Validation](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html)
