#!/usr/bin/env python3
"""
Track outreach status in a local CSV.

Usage:
    python check_status.py
    python check_status.py --tracker tracker.csv
    python check_status.py --mark-bounced person@example.com
    python check_status.py --mark-replied person@example.com
    python check_status.py --add-note person@example.com "Asked me to follow up next week"
"""

import argparse
import csv
from datetime import datetime
from pathlib import Path

from config import SEND_SETTINGS


FIELDNAMES = ["name", "company", "email", "sent_date", "status", "replied", "bounced", "notes"]


def normalize_bool(value):
    return (value or "").strip().lower() in {"1", "true", "yes", "y"}


def load_tracker(path):
    tracker_path = Path(path)
    if not tracker_path.exists():
        return []

    with open(tracker_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            normalized = {field: (row.get(field) or "").strip() for field in FIELDNAMES}
            rows.append(normalized)
        return rows


def save_tracker(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def print_summary(rows):
    total = len(rows)
    sent = sum(1 for row in rows if row["status"] == "sent")
    sending = sum(1 for row in rows if row["status"] == "sending")
    replied = sum(1 for row in rows if normalize_bool(row["replied"]) or row["status"] == "replied")
    bounced = sum(1 for row in rows if normalize_bool(row["bounced"]) or row["status"] == "bounced")
    awaiting_reply = max(sent - replied - bounced, 0)

    print(f"\n{'=' * 50}")
    print(f"  OUTREACH TRACKER - {datetime.now().strftime('%Y-%m-%d')}")
    print(f"{'=' * 50}")
    print(f"  Total contacts:    {total}")
    print(f"  Sent:              {sent}")
    print(f"  Still sending:     {sending}")
    print(f"  Replied:           {replied}")
    print(f"  Bounced:           {bounced}")
    print(f"  Awaiting reply:    {awaiting_reply}")
    print(f"  Response rate:     {replied / sent * 100:.1f}%" if sent else "  Response rate:     N/A")
    print(f"{'=' * 50}\n")

    for label, predicate in [
        ("REPLIED", lambda row: normalize_bool(row["replied"]) or row["status"] == "replied"),
        ("BOUNCED", lambda row: normalize_bool(row["bounced"]) or row["status"] == "bounced"),
    ]:
        matches = [row for row in rows if predicate(row)]
        if not matches:
            continue
        print(f"  {label}:")
        for row in matches:
            note = f" - {row['notes']}" if row["notes"] else ""
            print(f"    {row['name']} @ {row['company']} ({row['email']}){note}")
        print()


def find_by_email(rows, email):
    email = email.strip().lower()
    for row in rows:
        if row["email"].lower() == email:
            return row
    return None


def mark_bounced(rows, email):
    row = find_by_email(rows, email)
    if not row:
        print(f"No entry found for {email}")
        return False
    row["bounced"] = "yes"
    row["status"] = "bounced"
    print(f"Marked {row['name']} @ {row['company']} as bounced")
    return True


def mark_replied(rows, email):
    row = find_by_email(rows, email)
    if not row:
        print(f"No entry found for {email}")
        return False
    row["replied"] = "yes"
    row["status"] = "replied"
    print(f"Marked {row['name']} @ {row['company']} as replied")
    return True


def add_note(rows, email, note):
    row = find_by_email(rows, email)
    if not row:
        print(f"No entry found for {email}")
        return False
    row["notes"] = note
    print(f"Added note to {row['name']} @ {row['company']}")
    return True


def build_parser():
    parser = argparse.ArgumentParser(description="Local outreach tracker")
    parser.add_argument("--tracker", default=SEND_SETTINGS["tracker_csv"], help="Tracker CSV path.")
    parser.add_argument("--mark-bounced", type=str, help="Mark an email as bounced.")
    parser.add_argument("--mark-replied", type=str, help="Mark an email as replied.")
    parser.add_argument("--add-note", nargs=2, metavar=("EMAIL", "NOTE"), help="Add a note to a tracker row.")
    return parser


def main():
    args = build_parser().parse_args()
    rows = load_tracker(args.tracker)

    changed = False
    if args.mark_bounced:
        changed = mark_bounced(rows, args.mark_bounced)
    elif args.mark_replied:
        changed = mark_replied(rows, args.mark_replied)
    elif args.add_note:
        changed = add_note(rows, args.add_note[0], args.add_note[1])
    else:
        print_summary(rows)
        return

    if changed:
        save_tracker(args.tracker, rows)


if __name__ == "__main__":
    main()
