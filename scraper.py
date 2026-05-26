#!/usr/bin/env python3
"""
Collect public contact leads into a contacts CSV.

The scraper starts from user-provided seed URLs. The user's request and target
roles guide filtering and personalization, while each row remains traceable to
the public page where the email or email format was found.

Usage:
    python scraper.py --request "AI founders in NYC" --url https://example.com
    python scraper.py --target-role founder --urls-file seeds.txt --append --crawl-pages 5
"""

import argparse
import csv
import re
import socket
import time
from collections import deque
from html.parser import HTMLParser
from pathlib import Path
from urllib import robotparser
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.request import Request, urlopen


CONTACT_FIELDS = [
    "name",
    "email",
    "company",
    "role",
    "company_description",
    "personalization",
    "source",
]

FIELD_ALIASES = {
    "name": ["name", "full_name", "contact_name", "person"],
    "email": ["email", "email_address", "work_email", "email_guess"],
    "company": ["company", "organization", "org", "account"],
    "role": ["role", "title", "job_title"],
    "company_description": ["company_description", "description", "company_context", "context"],
    "personalization": ["personalization", "icebreaker", "opening", "note"],
    "source": ["source", "linkedin", "url", "website"],
}

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
NAME_ROLE_RE = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b.{0,80}?"
    r"\b(Founder|Co-Founder|Cofounder|CEO|CTO|COO|CMO|Head of [A-Za-z ]+|VP [A-Za-z ]+|"
    r"Director [A-Za-z ]+|Recruiter|Talent|Hiring Manager|Engineer|Developer)\b",
    re.IGNORECASE,
)
PUBLIC_FORMAT_RE = re.compile(
    r"(?:email\s+)?format\s*(?:is|:)?\s*([a-z._+-]+)@([a-z0-9.-]+\.[a-z]{2,})",
    re.IGNORECASE,
)

SKIP_EMAIL_PREFIXES = {"example", "test", "hello@example", "you"}
PLACEHOLDER_LOCAL_PARTS = {
    "first",
    "firstname",
    "first.last",
    "firstname.lastname",
    "first_last",
    "firstname_lastname",
    "firstlast",
    "flast",
    "name",
    "user",
}
ROLE_EMAIL_PREFIXES = {"careers", "jobs", "recruiting", "talent", "founders", "team", "press", "hello", "info"}
SKIP_EXTENSIONS = {
    ".css",
    ".js",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
}


class PageParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.title_parts = []
        self.description = ""
        self.text_parts = []
        self.links = []
        self.mailto_emails = []
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        attr_map = {name.lower(): value for name, value in attrs if value}
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = attr_map.get("name", "").lower()
            prop = attr_map.get("property", "").lower()
            if name == "description" or prop == "og:description":
                self.description = attr_map.get("content", "").strip()
        elif tag == "a":
            href = attr_map.get("href", "").strip()
            if not href:
                return
            if href.lower().startswith("mailto:"):
                self.mailto_emails.extend(extract_emails(href))
                return
            absolute_url = normalize_url(urljoin(self.base_url, href))
            if absolute_url:
                self.links.append(absolute_url)

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        text = " ".join(data.split())
        if not text:
            return
        if self._in_title:
            self.title_parts.append(text)
        self.text_parts.append(text)

    @property
    def title(self):
        return " ".join(self.title_parts).strip()

    @property
    def text(self):
        return " ".join(self.text_parts)


def normalize_url(value):
    value = value.strip()
    if not value:
        return ""
    if "://" not in value:
        value = f"https://{value}"
    value, _fragment = urldefrag(value)
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return value


def registrable_domain(url_or_domain):
    value = url_or_domain.strip().lower()
    if "://" in value:
        value = urlparse(value).netloc
    value = value.split("@")[-1].split(":")[0].removeprefix("www.")
    parts = value.split(".")
    if len(parts) < 2:
        return value
    return ".".join(parts[-2:])


def same_domain(left, right):
    return registrable_domain(left) == registrable_domain(right)


def looks_like_page(url):
    path = urlparse(url).path.lower()
    return not any(path.endswith(extension) for extension in SKIP_EXTENSIONS)


def extract_emails(text):
    emails = []
    for match in EMAIL_RE.findall(text):
        email = match.strip(".,;:()[]{}<>").lower()
        local_part = email.split("@", 1)[0]
        if any(email.startswith(prefix) for prefix in SKIP_EMAIL_PREFIXES):
            continue
        if local_part in PLACEHOLDER_LOCAL_PARTS:
            continue
        emails.append(email)
    return sorted(set(emails))


def email_domain(email):
    return email.rsplit("@", 1)[-1].lower()


def domain_resolves(domain):
    try:
        socket.getaddrinfo(domain, 80)
        return True
    except OSError:
        return False


def verified_email(email, seed_url, args, domain_cache):
    domain = email_domain(email)
    seed_domain = registrable_domain(seed_url)

    if args.verify_domain and registrable_domain(domain) != seed_domain:
        return False

    if args.resolve_domains:
        cached = domain_cache.get(domain)
        if cached is None:
            cached = domain_resolves(domain)
            domain_cache[domain] = cached
        if not cached:
            return False

    return True


def guess_company(url, title, fallback=""):
    if fallback:
        return fallback

    if title:
        for separator in [" | ", " - ", " -- ", " :: "]:
            if separator in title:
                return title.split(separator)[0].strip()
        return title.strip()

    domain = urlparse(url).netloc.replace("www.", "")
    return domain.split(".", 1)[0].replace("-", " ").title()


def request_keywords(args):
    terms = []
    for value in [args.request, args.company_description, *args.target_role]:
        terms.extend(re.findall(r"[a-z0-9]+", value.lower()))
    return {term for term in terms if len(term) > 2}


def page_matches_request(text, args):
    keywords = request_keywords(args)
    if not keywords:
        return True
    text_words = set(re.findall(r"[a-z0-9]+", text.lower()))
    return bool(keywords & text_words)


def infer_role(email, text):
    local_part = email.split("@", 1)[0].lower()
    for prefix in ROLE_EMAIL_PREFIXES:
        if local_part == prefix or local_part.startswith(f"{prefix}."):
            return prefix.replace("-", " ").title()

    for match in NAME_ROLE_RE.finditer(text):
        name, role = match.groups()
        if email_local_matches_name(local_part, name):
            return normalize_role(role)

    return ""


def email_local_matches_name(local_part, name):
    parts = [part.lower() for part in re.findall(r"[A-Za-z]+", name)]
    if len(parts) < 2:
        return False
    first, last = parts[0], parts[-1]
    candidates = {
        first,
        f"{first}.{last}",
        f"{first}{last}",
        f"{first[0]}{last}",
        f"{first}_{last}",
        f"{first}-{last}",
    }
    return local_part in candidates


def normalize_role(role):
    return " ".join(role.split()).replace("Cofounder", "Co-Founder")


def extract_people(text, args):
    people = []
    seen = set()
    target_roles = [role.lower() for role in args.target_role]

    for match in NAME_ROLE_RE.finditer(text):
        name, role = match.groups()
        role = normalize_role(role)
        if target_roles and not any(target in role.lower() for target in target_roles):
            continue
        key = (name.lower(), role.lower())
        if key in seen:
            continue
        seen.add(key)
        people.append({"name": name, "role": role})

    return people


def detect_email_patterns(emails, page_text):
    patterns = []

    for match in PUBLIC_FORMAT_RE.finditer(page_text):
        local_format, domain = match.groups()
        normalized = normalize_pattern(local_format)
        if normalized:
            patterns.append((normalized, domain.lower()))

    for email in emails:
        local_part, domain = email.split("@", 1)
        pattern = pattern_from_local_part(local_part)
        if pattern:
            patterns.append((pattern, domain))

    deduped = []
    seen = set()
    for pattern in patterns:
        if pattern not in seen:
            seen.add(pattern)
            deduped.append(pattern)
    return deduped


def normalize_pattern(local_format):
    value = local_format.lower().strip()
    replacements = {
        "first.last": "first.last",
        "firstname.lastname": "first.last",
        "first_last": "first_last",
        "firstname_lastname": "first_last",
        "firstlast": "firstlast",
        "firstname": "first",
        "first": "first",
        "flast": "flast",
        "firstinitiallastname": "flast",
    }
    return replacements.get(value)


def pattern_from_local_part(local_part):
    if local_part in ROLE_EMAIL_PREFIXES:
        return ""
    if "." in local_part and all(part.isalpha() for part in local_part.split(".", 1)):
        return "first.last"
    if "_" in local_part and all(part.isalpha() for part in local_part.split("_", 1)):
        return "first_last"
    if re.fullmatch(r"[a-z][a-z]+", local_part):
        return "first"
    return ""


def apply_pattern(name, pattern, domain):
    parts = [part.lower() for part in re.findall(r"[A-Za-z]+", name)]
    if len(parts) < 2:
        return ""
    first, last = parts[0], parts[-1]
    if pattern == "first.last":
        local_part = f"{first}.{last}"
    elif pattern == "first_last":
        local_part = f"{first}_{last}"
    elif pattern == "firstlast":
        local_part = f"{first}{last}"
    elif pattern == "flast":
        local_part = f"{first[0]}{last}"
    elif pattern == "first":
        local_part = first
    else:
        return ""
    return f"{local_part}@{domain}"


def build_personalization(company, role, description, source, request):
    if request and role:
        return f"I found {company} while researching {request}, and your {role} work looked relevant."
    if request:
        return f"I found {company} while researching {request}."
    if description and description != company:
        return f"I came across {company}'s work on {description}."
    return f"I came across {company} while researching {source}."


def can_fetch(url, user_agent, robots_cache):
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = robots_cache.get(robots_url)

    if parser is None:
        parser = robotparser.RobotFileParser()
        parser.set_url(robots_url)
        try:
            parser.read()
        except Exception:
            return True
        robots_cache[robots_url] = parser

    return parser.can_fetch(user_agent, url)


def fetch_page(url, user_agent, timeout):
    request = Request(url, headers={"User-Agent": user_agent})
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type and "text/plain" not in content_type:
            return ""
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def scrape_seed(seed_url, args, robots_cache, domain_cache):
    queue = deque([seed_url])
    visited = set()
    rows = []

    while queue and len(visited) < args.crawl_pages:
        url = queue.popleft()
        if url in visited or not looks_like_page(url):
            continue
        visited.add(url)

        if not args.ignore_robots and not can_fetch(url, args.user_agent, robots_cache):
            print(f"Skipping disallowed URL: {url}")
            continue

        try:
            html = fetch_page(url, args.user_agent, args.timeout)
        except Exception as exc:
            print(f"Failed to fetch {url}: {exc}")
            continue

        parser = PageParser(url)
        parser.feed(html)

        page_text = parser.text
        if not page_matches_request(" ".join([page_text, parser.title, parser.description]), args):
            add_same_domain_links(seed_url, parser.links, queue, visited, args.crawl_pages)
            time.sleep(args.delay)
            continue

        public_emails = [
            email
            for email in sorted(set(parser.mailto_emails + extract_emails(page_text)))
            if verified_email(email, seed_url, args, domain_cache)
        ]
        company = guess_company(url, parser.title, args.company)
        description = args.company_description or parser.description or company

        for email in public_emails:
            role = infer_role(email, page_text)
            rows.append(
                {
                    "name": "",
                    "email": email,
                    "company": company,
                    "role": role,
                    "company_description": description,
                    "personalization": build_personalization(company, role, description, url, args.request),
                    "source": url,
                }
            )

        if args.infer_from_format:
            people = extract_people(page_text, args)
            patterns = detect_email_patterns(public_emails, page_text)
            for person in people:
                for pattern, domain in patterns[: args.max_patterns]:
                    email = apply_pattern(person["name"], pattern, domain)
                    if not email or not verified_email(email, seed_url, args, domain_cache):
                        continue
                    rows.append(
                        {
                            "name": person["name"],
                            "email": email,
                            "company": company,
                            "role": person["role"],
                            "company_description": description,
                            "personalization": build_personalization(
                                company,
                                person["role"],
                                description,
                                url,
                                args.request,
                            ),
                            "source": f"{url} (inferred from public email format: {pattern}@{domain})",
                        }
                    )

        add_same_domain_links(seed_url, parser.links, queue, visited, args.crawl_pages)
        time.sleep(args.delay)

    return rows


def add_same_domain_links(seed_url, links, queue, visited, crawl_pages):
    for link in links:
        if len(visited) + len(queue) >= crawl_pages:
            break
        if same_domain(seed_url, link) and link not in visited and looks_like_page(link):
            queue.append(link)


def read_seed_urls(args):
    urls = [normalize_url(url) for url in args.url]
    if args.urls_file:
        for line in Path(args.urls_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(normalize_url(line))
    return [url for url in urls if url]


def read_existing_rows(path):
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def first_present(row, aliases):
    for alias in aliases:
        value = row.get(alias)
        if value and value.strip():
            return value.strip()
    return ""


def merge_rows(existing_rows, scraped_rows):
    merged = []
    seen_emails = set()

    for row in existing_rows + scraped_rows:
        canonical = {}
        for field in CONTACT_FIELDS:
            canonical[field] = first_present(row, FIELD_ALIASES.get(field, [field]))

        email = canonical["email"].lower()
        if not email or email in seen_emails:
            continue
        seen_emails.add(email)
        merged.append(canonical)

    return merged


def write_rows(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CONTACT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def build_parser():
    parser = argparse.ArgumentParser(description="Scrape public emails into contacts.csv")
    parser.add_argument("--request", default="", help="User request, e.g. 'AI founders in NYC'.")
    parser.add_argument("--target-role", action="append", default=[], help="Role to look for. Can be repeated.")
    parser.add_argument("--url", action="append", default=[], help="Seed URL. Can be passed multiple times.")
    parser.add_argument("--urls-file", help="Text file of seed URLs, one per line.")
    parser.add_argument("--output", default="contacts.csv", help="Output contacts CSV path.")
    parser.add_argument("--append", action="store_true", help="Merge with an existing output CSV.")
    parser.add_argument("--company", default="", help="Override company name for all scraped rows.")
    parser.add_argument("--company-description", default="", help="Override company description.")
    parser.add_argument("--crawl-pages", type=int, default=1, help="Max same-domain pages to fetch per seed URL.")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between page fetches in seconds.")
    parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout in seconds.")
    parser.add_argument("--user-agent", default="cold-email-maxxxing/1.0", help="User-Agent for requests.")
    parser.add_argument("--ignore-robots", action="store_true", help="Do not check robots.txt.")
    parser.add_argument("--no-verify-domain", dest="verify_domain", action="store_false", help="Allow emails outside the seed URL's domain.")
    parser.add_argument("--resolve-domains", action="store_true", help="Check that email domains resolve in DNS.")
    parser.add_argument("--infer-from-format", action="store_true", help="Infer named emails from a public email format found on the same domain.")
    parser.add_argument("--max-patterns", type=int, default=2, help="Max detected email patterns to try per person.")
    parser.set_defaults(verify_domain=True)
    return parser


def main():
    args = build_parser().parse_args()
    seeds = read_seed_urls(args)
    if not seeds:
        raise SystemExit("Provide at least one --url or --urls-file.")

    robots_cache = {}
    domain_cache = {}
    scraped_rows = []
    for seed in seeds:
        scraped_rows.extend(scrape_seed(seed, args, robots_cache, domain_cache))

    output_path = Path(args.output)
    existing_rows = read_existing_rows(output_path) if args.append else []
    rows = merge_rows(existing_rows, scraped_rows)
    write_rows(output_path, rows)

    print(f"Wrote {len(rows)} contacts to {output_path}")
    if not scraped_rows:
        print("No matching public emails found. Try contact/about/team pages or adjust --request/--target-role.")


if __name__ == "__main__":
    main()
