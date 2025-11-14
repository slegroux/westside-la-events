#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
"""
Fix the existing database by updating FTS triggers.
This script will recreate the triggers to fix the update issue.
"""
import sqlite3

def fix_database(db_path='./data/events.db'):
    """Fix FTS triggers in the database."""
    print(f"Fixing database triggers in: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Drop old triggers
        print("Dropping old triggers...")
        cursor.execute("DROP TRIGGER IF EXISTS events_ai")
        cursor.execute("DROP TRIGGER IF EXISTS events_ad")
        cursor.execute("DROP TRIGGER IF EXISTS events_au")
        cursor.execute("DROP TRIGGER IF EXISTS events_bu")

        # Create new triggers with correct approach
        print("Creating INSERT trigger...")
        cursor.execute("""
            CREATE TRIGGER events_ai AFTER INSERT ON events BEGIN
                INSERT INTO events_fts(rowid, title, description, venue_name)
                VALUES (new.id, new.title, new.description, new.venue_name);
            END
        """)

        print("Creating DELETE trigger...")
        cursor.execute("""
            CREATE TRIGGER events_ad AFTER DELETE ON events BEGIN
                DELETE FROM events_fts WHERE rowid = old.id;
            END
        """)

        print("Creating UPDATE triggers (BEFORE and AFTER)...")
        cursor.execute("""
            CREATE TRIGGER events_bu BEFORE UPDATE ON events BEGIN
                DELETE FROM events_fts WHERE rowid = old.id;
            END
        """)

        cursor.execute("""
            CREATE TRIGGER events_au AFTER UPDATE ON events BEGIN
                INSERT INTO events_fts(rowid, title, description, venue_name)
                VALUES (new.id, new.title, new.description, new.venue_name);
            END
        """)

        conn.commit()
        print("✓ Triggers fixed successfully!")

        # Test update works
        print("\nTesting update...")
        cursor.execute("SELECT id, title FROM events LIMIT 1")
        row = cursor.fetchone()
        if row:
            test_id = row[0]
            cursor.execute("UPDATE events SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (test_id,))
            conn.commit()
            print(f"✓ Test update successful on event ID {test_id}")
        else:
            print("No events in database to test")

    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    fix_database()
