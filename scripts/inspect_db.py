#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
"""Quick database inspection script"""
import sqlite3
import sys

def inspect_database(db_path='data/events.db'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get table info
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"📊 Tables: {[t[0] for t in tables]}\n")

    # Get event count
    cursor.execute('SELECT COUNT(*) FROM events')
    total = cursor.fetchone()[0]
    print(f"📝 Total events: {total}\n")

    # Count by source
    cursor.execute('SELECT source, COUNT(*) FROM events GROUP BY source ORDER BY COUNT(*) DESC')
    print("📍 Events by source:")
    for source, count in cursor.fetchall():
        print(f"  {source}: {count}")

    # Count by category
    cursor.execute('SELECT category, COUNT(*) FROM events WHERE category IS NOT NULL GROUP BY category ORDER BY COUNT(*) DESC')
    print("\n🏷️  Events by category:")
    for cat, count in cursor.fetchall():
        print(f"  {cat}: {count}")

    # Recent events
    cursor.execute('''
        SELECT id, title, event_date, venue_name, source
        FROM events
        ORDER BY created_at DESC
        LIMIT 10
    ''')
    print("\n🆕 Most recently added events:")
    for row in cursor.fetchall():
        id, title, date, venue, source = row
        title_short = title[:60] + '...' if len(title) > 60 else title
        print(f"  [{id}] {title_short}")
        print(f"       📅 {date} | 📍 {venue} | 🔗 {source}")

    # Upcoming events
    cursor.execute('''
        SELECT COUNT(*) FROM events
        WHERE event_date >= date('now')
    ''')
    upcoming = cursor.fetchone()[0]
    print(f"\n📅 Upcoming events: {upcoming}")

    conn.close()

if __name__ == '__main__':
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'data/events.db'
    inspect_database(db_path)
