#!/usr/bin/env python3
"""
Cold email CLI.

Usage:
    python send_emails.py --dry-run
    python send_emails.py --send
    python send_emails.py --preview "Jane"
    python send_emails.py --csv contacts.csv --template concise
"""

import argparse
import csv
import smtplib
import time
from datetime import datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from config import ROOT_DIR, SEND_SETTINGS, SENDER, SMTP
from email_templates import TEMPLATES


FIELD_ALIASES = {
    "name": ["name", "full_name", "contact_name", "person"],
    "email": ["email", "email_address", "work_email", "email_guess"],
    "company": ["company", "organization", "org", "account"],
    "role": ["role", "title", "job_title"],
    "company_description": ["company_description", "description", "company_context", "context"],
    "personalization": ["personalization", "icebreaker", "opening", "note"],
    "source": ["source", "linkedin", "url", "website"],
}


class SafeDict(dict):
    def __missing__(self, key):
        return ""


def first_present(row, aliases, default=""):
    for alias in aliases:
        value = row.get(alias)
        if value and value.strip():
            return value.strip()
    return default


def normalize_contact(row):
    normalized = {key: (value or "").strip() for key, value in row.items()}
    for field, aliases in FIELD_ALIASES.items():
        normalized[field] = first_present(normalized, aliases)

    if not normalized["email"]:
        return None

    if not normalized["name"]:
        normalized["name"] = normalized["email"].split("@", 1)[0]

    if not normalized["company"]:
        normalized["company"] = "your team"

    if not normalized["company_description"]:
        normalized["company_description"] = normalized["company"]

    if not normalized["personalization"]:
        normalized["personalization"] = f"I came across {normalized['company']} and wanted to reach out."

    normalized["first_name"] = normalized["name"].split()[0]
    normalized["focus_area"] = normalized["company_description"].split(",", 1)[0]
    return normalized


def load_contacts(csv_path):
    contacts = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"{csv_path} has no header row")

        for row_number, row in enumerate(reader, start=2):
            contact = normalize_contact(row)
            if contact is None:
                print(f"Skipping row {row_number}: missing email")
                continue
            contacts.append(contact)

    return contacts


def auto_select_template(contact):
    text = " ".join(
        [
            contact.get("role", ""),
            contact.get("company_description", ""),
            contact.get("personalization", ""),
        ]
    ).lower()

    technical_keywords = ["api", "ai", "ml", "data", "developer", "engineering", "infrastructure"]
    if any(keyword in text for keyword in technical_keywords):
        return "technical"
    return "general"


def template_context(contact):
    bullet_points = "\n".join(f"- {item}" for item in SENDER["bullet_points"])
    context = SafeDict(contact)
    context.update(
        {
            "sender_name": SENDER["name"],
            "sender_email": SENDER["email"],
            "sender_background": SENDER["background"],
            "sender_project": SENDER["project"],
            "sender_goal": SENDER["goal"],
            "sender_links": SENDER["links"],
            "bullet_points": bullet_points,
        }
    )
    return context


def personalize_email(contact, template_key=None):
    selected_template = template_key or auto_select_template(contact)
    template = TEMPLATES[selected_template]
    context = template_context(contact)
    subject = template["subject"].format_map(context)
    body = template["body"].format_map(context)
    return subject, body, selected_template


def resolve_attachment_path(path_value):
    if not path_value:
        return None
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


def attach_file(msg, attachment_path, attachment_filename):
    if not attachment_path:
        return False

    if not attachment_path.exists():
        print(f"WARNING: attachment not found at {attachment_path}")
        return False

    with open(attachment_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())

    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f"attachment; filename={attachment_filename}")
    msg.attach(part)
    return True


def send_email(contact, subject, body, dry_run=True, attach=True):
    attachment_path = resolve_attachment_path(SEND_SETTINGS["resume_path"])
    attachment_name = SEND_SETTINGS["attachment_filename"]
    has_attachment = attach and attachment_path is not None

    if dry_run:
        print(f"\n{'=' * 60}")
        print(f"TO: {contact['email']}")
        print(f"SUBJECT: {subject}")
        print(f"ATTACHMENT: {attachment_name if has_attachment else 'None'}")
        print(f"{'=' * 60}")
        print(body)
        print(f"{'=' * 60}\n")
        return True

    if not SMTP["password"]:
        print("ERROR: set SMTP_PASSWORD or GMAIL_APP_PASSWORD before sending")
        return False

    msg = MIMEMultipart()
    msg["From"] = f"{SENDER['name']} <{SMTP['email']}>"
    msg["To"] = contact["email"]
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    if attach:
        attach_file(msg, attachment_path, attachment_name)

    try:
        with smtplib.SMTP(SMTP["server"], SMTP["port"]) as server:
            server.starttls()
            server.login(SMTP["email"], SMTP["password"])
            server.send_message(msg)
        print(f"SENT to {contact['email']}")
        return True
    except Exception as exc:
        print(f"FAILED to send to {contact['email']}: {exc}")
        return False


def log_sent(contact, subject, status, template_key):
    log_file = SEND_SETTINGS["sent_log_csv"]
    file_exists = Path(log_file).exists()

    with open(log_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "name", "company", "email", "subject", "template", "status"])
        writer.writerow(
            [
                datetime.now().isoformat(timespec="seconds"),
                contact["name"],
                contact["company"],
                contact["email"],
                subject,
                template_key,
                status,
            ]
        )


def build_parser():
    parser = argparse.ArgumentParser(description="Personalized cold email sender")
    parser.add_argument("--send", action="store_true", help="Actually send emails. Default is dry-run.")
    parser.add_argument("--dry-run", action="store_true", help="Preview emails without sending.")
    parser.add_argument("--preview", type=str, help="Preview contacts matching this name, email, or company.")
    parser.add_argument("--csv", default=SEND_SETTINGS["contacts_csv"], help="Contacts CSV path.")
    parser.add_argument("--template", choices=TEMPLATES.keys(), help="Template to use. Defaults to auto-select.")
    parser.add_argument("--limit", type=int, default=SEND_SETTINGS["daily_limit"], help="Maximum contacts to process.")
    parser.add_argument("--delay", type=int, default=SEND_SETTINGS["delay_between_emails_sec"], help="Delay between sent emails.")
    parser.add_argument("--no-attach", action="store_true", help="Do not attach the configured file.")
    parser.add_argument("--list-templates", action="store_true", help="Print available template names.")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.list_templates:
        print("\n".join(TEMPLATES.keys()))
        return

    dry_run = not args.send
    contacts = load_contacts(args.csv)

    if args.preview:
        needle = args.preview.lower()
        contacts = [
            contact
            for contact in contacts
            if needle in contact["name"].lower()
            or needle in contact["email"].lower()
            or needle in contact["company"].lower()
        ]
        if not contacts:
            print(f"No contact matching '{args.preview}' found in {args.csv}")
            return

    contacts = contacts[: args.limit]

    print(f"{'DRY RUN' if dry_run else 'SENDING'} - {len(contacts)} contacts")
    print(f"Template: {args.template or 'auto-select'}")

    if not dry_run:
        print(f"Delay between emails: {args.delay}s")
        confirm = input("\nType 'yes' to confirm sending: ")
        if confirm != "yes":
            print("Aborted.")
            return

    processed_count = 0
    for index, contact in enumerate(contacts, start=1):
        subject, body, template_key = personalize_email(contact, args.template)
        success = send_email(contact, subject, body, dry_run=dry_run, attach=not args.no_attach)

        status = "sent" if success else "failed"
        if not dry_run:
            log_sent(contact, subject, status, template_key)

        if success:
            processed_count += 1

        if not dry_run and index < len(contacts):
            time.sleep(args.delay)

    action = "previewed" if dry_run else "sent"
    print(f"\nDone. {processed_count}/{len(contacts)} emails {action}.")


if __name__ == "__main__":
    main()
