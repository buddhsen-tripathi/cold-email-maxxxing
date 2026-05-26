"""
Configuration for the cold email CLI.

Values can be set in the environment or in a local .env file. Keep real
credentials and recipient data out of Git.
"""

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent


def load_dotenv(path=ROOT_DIR / ".env"):
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def env(name, default=""):
    return os.environ.get(name, default)


def env_int(name, default):
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    return int(value)


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def env_list(name, default=None):
    value = os.environ.get(name)
    if not value:
        return default or []
    return [item.strip() for item in value.split("||") if item.strip()]


load_dotenv()

SENDER = {
    "name": env("SENDER_NAME", "Your Name"),
    "email": env("SENDER_EMAIL", "you@example.com"),
    "background": env("SENDER_BACKGROUND", "a builder interested in your work"),
    "project": env("SENDER_PROJECT", "relevant products and systems"),
    "goal": env("OUTREACH_GOAL", "explore whether there is a fit"),
    "links": env("SENDER_LINKS", "Portfolio: https://example.com"),
    "bullet_points": env_list(
        "SENDER_BULLET_POINTS",
        [
            "Project one - one-line proof point",
            "Project two - one-line proof point",
            "Relevant experience - one-line proof point",
        ],
    ),
}

SMTP = {
    "server": env("SMTP_SERVER", "smtp.gmail.com"),
    "port": env_int("SMTP_PORT", 587),
    "email": env("SMTP_EMAIL", SENDER["email"]),
    "password": env("SMTP_PASSWORD", env("GMAIL_APP_PASSWORD", "")),
}

SEND_SETTINGS = {
    "contacts_csv": env("CONTACTS_CSV", "contacts.csv"),
    "sent_log_csv": env("SENT_LOG_CSV", "sent_log.csv"),
    "tracker_csv": env("TRACKER_CSV", "tracker.csv"),
    "resume_path": env("ATTACHMENT_PATH", ""),
    "attachment_filename": env("ATTACHMENT_FILENAME", "attachment.pdf"),
    "delay_between_emails_sec": env_int("DELAY_BETWEEN_EMAILS_SEC", 45),
    "daily_limit": env_int("DAILY_LIMIT", 20),
    "dry_run": env_bool("DRY_RUN", True),
}
