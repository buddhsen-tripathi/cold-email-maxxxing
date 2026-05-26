# Agent Instructions

This repo is designed for local, user-controlled cold outreach. Agents should help users collect accurate public contact data, populate `contacts.csv`, preview messages, and avoid committing private data.

## Core Rules

- Do not invent names, emails, roles, funding details, personalization, or sources.
- Use only public, unauthenticated sources unless the user explicitly provides material to use.
- Respect robots.txt, site terms, rate limits, and paywalls. Do not bypass CAPTCHAs, login walls, scraping protections, or blocked APIs.
- Prefer quality over volume. A small CSV with verified contacts is better than a large CSV of guesses.
- Never commit `.env`, `*.csv`, PDFs, logs, private resumes, or scraped recipient data.
- Keep each row traceable with a `source` URL.

## Contacts Schema

Populate a local `contacts.csv` with this header:

```csv
name,email,company,role,company_description,personalization,source
```

Field guidance:

- `name`: Person's full name if publicly available.
- `email`: Public email address. Required by `send_emails.py`.
- `company`: Organization or team name.
- `role`: Public title, such as Founder, CTO, Recruiter, Hiring Manager.
- `company_description`: Short factual company context.
- `personalization`: One specific, truthful opening detail for the email.
- `source`: URL where the contact or context was found.

## Recommended Workflow

1. Ask the user for the target segment, such as industry, geography, company stage, role, and maximum contact count.
2. Create or update a seed URL list in a local ignored file, such as `seeds.txt`.
3. Run the scraper against public company/contact/team pages:

```sh
python scraper.py --request "USER REQUEST HERE" --target-role founder --urls-file seeds.txt --output contacts.csv --append --crawl-pages 5
```

4. Review `contacts.csv` manually. Remove generic inboxes if the campaign needs named contacts.
5. Enrich missing fields only from public sources. Do not infer emails unless the user explicitly asks for public-format inference and accepts the risk.
6. Preview before sending:

```sh
python send_emails.py --dry-run --csv contacts.csv --limit 5
```

7. Fix weak personalization before any real send.

## Scraping Guidance

Good seed pages:

- Company home pages
- Contact pages
- About pages
- Team pages
- Public directories where scraping is allowed
- Public portfolio pages

Avoid:

- Login-only pages
- Sites that disallow crawling
- Personal social profiles unless the user provides the exact URLs and the platform allows the use
- Bulk harvesting pages with unclear consent or provenance

The scraper extracts public emails from page text and `mailto:` links. It verifies that email domains match the seed domain by default. It can also use `--resolve-domains` to check whether email domains resolve in DNS.

If the user explicitly wants email pattern inference, use:

```sh
python scraper.py --request "USER REQUEST HERE" --target-role founder --urls-file seeds.txt --output contacts.csv --append --crawl-pages 5 --infer-from-format
```

Only use pattern inference when the public page exposes an email format or a same-domain public email that reveals a format. Keep inferred rows because the `source` field marks them as inferred from public format. Do not describe inferred emails as verified deliverable addresses.

## Personalization Guidance

The `personalization` field should be one truthful sentence based on the user's request and public source context. Good examples:

- `I found Acme while researching AI infrastructure founders, and your Founder work looked relevant.`
- `I came across Acme's work on developer observability.`

Avoid:

- Claims that require private knowledge.
- Fake compliments.
- Generic filler that could apply to any company.
- Funding, hiring, or product claims unless the source directly supports them.

## Quality Bar

Before handing results back to the user, check:

- Every row has an `email`.
- Every row has a `company`.
- `source` points to where the data came from.
- Inferred emails are clearly marked in `source`.
- `personalization` is truthful and not generic filler.
- No private or sensitive files are staged in Git.

Useful commands:

```sh
python send_emails.py --dry-run --csv contacts.csv --limit 3
git status --short --ignored
```

## Commit Hygiene

Source files and docs can be committed. Local campaign data must stay ignored.

Commit candidates:

- `README.md`
- `AGENTS.md`
- `.env.example`
- `.gitignore`
- `*.py`

Do not commit:

- `.env`
- `contacts.csv`
- `tracker.csv`
- `sent_log.csv`
- `*.pdf`
- scraped datasets
