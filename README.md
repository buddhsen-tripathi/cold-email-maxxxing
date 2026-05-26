# Cold Email Maxxxing

A small, dependency-free Python CLI for personalized cold outreach. It reads a local contacts CSV, renders reusable email templates, previews messages by default, and can send through any SMTP server when you explicitly opt in.

## Features

- Dry-run previews by default
- SMTP sending with confirmation prompt
- Reusable templates in `email_templates.py`
- Environment-based sender configuration
- Flexible CSV column names
- Public email scraper for seed URLs
- Optional attachment support
- Local sent log and status tracker

## Requirements

- Python 3.9+
- An SMTP account, such as Gmail with an app password, if you want to send real emails

No third-party Python packages are required.

## Setup

Clone the repo, then create your local environment file:

```sh
cp .env.example .env
```

Edit `.env` with your sender details. At minimum, set:

```sh
SENDER_NAME="Your Name"
SENDER_EMAIL="you@example.com"
SMTP_EMAIL="you@example.com"
SMTP_PASSWORD="your-smtp-or-app-password"
```

For Gmail, use an app password rather than your normal account password.

## Contacts CSV

Create a local `contacts.csv`. CSV files are ignored by Git so recipient data does not get committed.

Required column:

- `email`

Recommended columns:

- `name`
- `company`
- `role`
- `company_description`
- `personalization`
- `source`

Compatible aliases are also supported:

- Email: `email`, `email_address`, `work_email`, `email_guess`
- Name: `name`, `full_name`, `contact_name`, `person`
- Company: `company`, `organization`, `org`, `account`
- Role: `role`, `title`, `job_title`
- Context: `company_description`, `description`, `company_context`, `context`
- Personalization: `personalization`, `icebreaker`, `opening`, `note`

Example:

```csv
name,email,company,role,company_description,personalization
Jane Doe,jane@example.com,Acme,Founder,"AI tools for finance","I liked your recent launch post."
```

## Preview Emails

Preview all contacts:

```sh
python send_emails.py --dry-run --csv contacts.csv
```

Preview one contact by name, email, or company:

```sh
python send_emails.py --preview jane --csv contacts.csv
```

Use a specific template:

```sh
python send_emails.py --dry-run --template concise --csv contacts.csv
```

List templates:

```sh
python send_emails.py --list-templates
```

## Send Emails

Sending is opt-in and requires typing `yes` at the confirmation prompt:

```sh
python send_emails.py --send --csv contacts.csv --limit 20 --delay 45
```

Use `--no-attach` to skip the configured attachment:

```sh
python send_emails.py --send --no-attach
```

## Attachments

Set these in `.env`:

```sh
ATTACHMENT_PATH="resume.pdf"
ATTACHMENT_FILENAME="Your_Name_Resume.pdf"
```

PDFs are ignored by Git by default.

## Tracking

View tracker summary:

```sh
python check_status.py --tracker tracker.csv
```

Mark a reply:

```sh
python check_status.py --mark-replied jane@example.com
```

Mark a bounce:

```sh
python check_status.py --mark-bounced jane@example.com
```

Add a note:

```sh
python check_status.py --add-note jane@example.com "Follow up next week"
```

The tracker expects these columns:

```csv
name,company,email,sent_date,status,replied,bounced,notes
```

## Safety Defaults

- `.env`, `*.csv`, `*.pdf`, logs, virtualenvs, and Python caches are ignored.
- The sender runs in dry-run mode unless you pass `--send`.
- Real sending requires SMTP credentials and an interactive confirmation.

## Customizing Templates

Edit `email_templates.py`. Templates use Python format fields, such as:

```text
Hi {first_name},

I came across {company} and was interested in {focus_area}.
```

Any CSV column can be referenced by name, and missing fields render as empty strings.

## Scraping Contacts

Use `scraper.py` to collect public email addresses from seed URLs into `contacts.csv`. Pass the user's target request so the scraper can filter page context and write better personalization:

```sh
python scraper.py --request "AI founders in NYC" --target-role founder --url https://example.com --output contacts.csv
```

Scrape multiple seed URLs from a local text file:

```sh
python scraper.py --request "developer tool founders" --target-role founder --urls-file seeds.txt --output contacts.csv --append --crawl-pages 5
```

Each seed URL is fetched with a delay, same-domain crawling is limited by `--crawl-pages`, robots.txt is checked by default, and email domains must match the seed domain by default.

Useful options:

```sh
python scraper.py --url https://example.com/contact --company "Example Inc" --company-description "Developer tooling company"
python scraper.py --urls-file seeds.txt --delay 2 --timeout 20
python scraper.py --url https://example.com/team --infer-from-format --target-role founder
```

By default, the scraper only writes emails it finds publicly in page text or `mailto:` links. With `--infer-from-format`, it may infer named emails when both conditions are true:

- A public email format is visible on the same domain, such as `first.last@example.com`.
- A matching person and role are found on the crawled page.

Inferred rows are marked in the `source` column and should be reviewed before sending. Use `--no-verify-domain` only when you intentionally want to keep emails from domains other than the seed URL's domain.

The scraper writes the standard contact columns:

```csv
name,email,company,role,company_description,personalization,source
```

The `personalization` field is generated from the request, company context, role, and source page. Example:

```text
I found Example Inc while researching developer tool founders, and your Founder work looked relevant.
```

For agent-assisted research, see `AGENTS.md`. It defines the workflow for Codex, Claude, and similar coding agents to gather public sources, populate `contacts.csv`, and avoid committing private campaign data.
