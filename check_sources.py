#!/usr/bin/env python3
"""Check what sources are in the database."""

from src.data.database import Database

def main():
    db = Database()

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Total events
        total = cursor.execute('SELECT COUNT(*) FROM events').fetchone()[0]
        print(f'Total events: {total}')

        # Events by source
        print('\nEvents by source:')
        for row in cursor.execute('SELECT source, COUNT(*) as count FROM events GROUP BY source ORDER BY count DESC').fetchall():
            print(f'  {row[0]}: {row[1]}')

        # Sample of recent events
        print('\nRecent events sample (10 most recent):')
        for row in cursor.execute('SELECT title, source, event_date FROM events ORDER BY created_at DESC LIMIT 10').fetchall():
            print(f'  [{row[1]}] {row[0]} - {row[2]}')

if __name__ == '__main__':
    main()
