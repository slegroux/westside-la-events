#!/usr/bin/env python3
"""
Demonstration script showing the FTS5 security fix.
Tests that malicious queries no longer crash the database.
"""
import sys
import tempfile
from datetime import datetime, timedelta

from src.data.database import Database, sanitize_fts_query
from src.data.models import Event


def main():
    """Test FTS5 query sanitization."""
    print("FTS5 Query Sanitization Security Test")
    print("=" * 50)
    print()

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    db = Database(db_path)

    # Add some test events
    print("Adding test events...")
    events = [
        Event(
            title="Live Music Concert",
            description="Jazz music performance at sunset",
            venue_name="Santa Monica Pier",
            event_date=datetime.now() + timedelta(days=1),
            source="test",
            category="Music"
        ),
        Event(
            title='Art Exhibition: "Modern Life"',
            description="Contemporary art showcase",
            venue_name="Gallery Space",
            event_date=datetime.now() + timedelta(days=2),
            source="test",
            category="Art"
        ),
    ]

    for event in events:
        db.insert_event(event)

    print(f"Added {len(events)} events\n")

    # Test malicious queries that would have caused FTS syntax errors
    malicious_queries = [
        ('test"', "Unmatched quote"),
        ('"broken', "Unmatched opening quote"),
        ('query AND', "Incomplete AND operator"),
        ('test OR', "Incomplete OR operator"),
        ('(((', "Unmatched parentheses"),
        ('NOT', "Standalone NOT operator"),
        ('*', "Wildcard alone"),
        ('test AND (broken', "Mixed operators and unmatched parens"),
        ('"test" OR "broken', "Mixed valid and invalid syntax"),
    ]

    print("Testing malicious queries:")
    print("-" * 50)

    all_passed = True
    for query, description in malicious_queries:
        print(f"\nQuery: {query!r}")
        print(f"Description: {description}")
        print(f"Sanitized: {sanitize_fts_query(query)}")

        try:
            results = db.search_events(query=query)
            print(f"✓ SUCCESS: Query processed without errors ({len(results)} results)")
        except Exception as e:
            print(f"✗ FAILED: {e}")
            all_passed = False

    # Test normal queries still work
    print("\n" + "=" * 50)
    print("Testing normal queries:")
    print("-" * 50)

    normal_queries = [
        ('music', "Simple keyword"),
        ('Art Exhibition', "Multi-word search"),
        ('jazz music', "Two keywords"),
    ]

    for query, description in normal_queries:
        print(f"\nQuery: {query!r}")
        print(f"Description: {description}")
        print(f"Sanitized: {sanitize_fts_query(query)}")

        try:
            results = db.search_events(query=query)
            print(f"✓ SUCCESS: {len(results)} results found")
            if results:
                for result in results[:2]:  # Show first 2 results
                    print(f"  - {result.title}")
        except Exception as e:
            print(f"✗ FAILED: {e}")
            all_passed = False

    # Summary
    print("\n" + "=" * 50)
    if all_passed:
        print("✓ All tests passed! FTS queries are properly sanitized.")
        return 0
    else:
        print("✗ Some tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
