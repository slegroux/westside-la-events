"""
Audit stored events for fabricated dates.

Three signatures of a scraper inventing a date rather than reading one:

  weekday_mismatch  The listing names a weekday ("Thursdays", "every Friday")
                    but the stored date falls on a different day. Catches both
                    fuzzy-parse-defaults-to-today and bad year inference
                    ("Thursday, April 9" bumped into a year where the 9th is a
                    Friday).

  anchored_to_today The date equals the day the row was written. A scraper that
                    defaults missing date parts to "now" produces one of these
                    every run, so the same title reappears on each scrape date.

  far_future        More than a year out. Usually a blind `year + 1` bump
                    applied to an event that had simply already happened.

Usage:
    micromamba run -n la python scripts/audit_event_dates.py [--db PATH]
"""
import argparse
import re
import sqlite3
from collections import defaultdict
from datetime import datetime

WEEKDAYS = {
    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
    'friday': 4, 'saturday': 5, 'sunday': 6,
}
WEEKDAY_RE = re.compile(
    r'\b(' + '|'.join(WEEKDAYS) + r')s?\b', re.IGNORECASE
)
FAR_FUTURE_DAYS = 400


def _parse(value):
    if not value:
        return None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d'):
        try:
            return datetime.strptime(value[:26], fmt)
        except ValueError:
            continue
    return None


# A weekday only pins the date when the listing is asserting *this* event's day
# ("this Saturday", "Saturday Night Comedy", "every Thursday"). A weekday
# mentioned loosely inside a long blurb says nothing, so those are ignored --
# otherwise the audit drowns in false positives.
BINDING_RE = re.compile(
    r'(?:\bthis\s+|\bevery\s+|\bon\s+)?\b(' + '|'.join(WEEKDAYS) + r')s?\b'
    r'(?=\s*(?:,|:|\s+night|\s+\d|\s*\||$))',
    re.IGNORECASE,
)


def named_weekday(title, description):
    """The weekday a listing binds this event to, if exactly one is asserted.

    Reads the title in full and only the opening of the description, where a
    source states the date ("Please join us this Saturday, December 13th").
    """
    found = set()
    for text in (title or '', (description or '')[:120]):
        for match in BINDING_RE.finditer(text):
            found.add(WEEKDAYS[match.group(1).lower()])
    return found.pop() if len(found) == 1 else None


def audit(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, source, title, description, event_date, updated_at "
        "FROM events WHERE event_date >= date('now')"
    ).fetchall()

    findings = defaultdict(lambda: defaultdict(list))
    # An event landing on the day it was written is unremarkable on its own --
    # plenty of events really are today. The signature of a scraper anchoring
    # to "now" is the *same* listing recurring across several scrape days, the
    # way one Oktoberfest listing reached prod 14 times over.
    anchored = defaultdict(list)
    now = datetime.now()

    for row in rows:
        start = _parse(row['event_date'])
        if not start:
            continue

        weekday = named_weekday(row['title'], row['description'])
        if weekday is not None and start.weekday() != weekday:
            findings[row['source']]['weekday_mismatch'].append(row)

        written = _parse(row['updated_at'])
        if written and start.date() == written.date():
            anchored[(row['source'], row['title'])].append(row)

        if (start - now).days > FAR_FUTURE_DAYS:
            findings[row['source']]['far_future'].append(row)

    for (source, _title), matches in anchored.items():
        if len({row['event_date'][:10] for row in matches}) >= 3:
            findings[source]['anchored_to_scrape_date'].extend(matches)

    conn.close()
    return findings, len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default='data/events.db')
    parser.add_argument('--show', type=int, default=2,
                        help='example rows to print per finding')
    args = parser.parse_args()

    findings, total = audit(args.db)
    print(f'Audited {total} upcoming events\n')

    if not findings:
        print('No suspicious dates found.')
        return 0

    flagged = 0
    for source in sorted(findings, key=lambda s: -sum(len(v) for v in findings[s].values())):
        counts = {k: len(v) for k, v in findings[source].items()}
        flagged += sum(counts.values())
        print(f'{source}: ' + ', '.join(f'{k}={n}' for k, n in sorted(counts.items())))
        for kind, rows in sorted(findings[source].items()):
            for row in rows[:args.show]:
                when = _parse(row['event_date'])
                print(f'    [{kind}] {when:%Y-%m-%d %a}  {row["title"][:52]}')

    print(f'\n{flagged} suspicious rows across {len(findings)} sources')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
