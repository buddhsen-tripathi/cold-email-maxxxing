"""
Reusable cold email templates.

Templates are formatted with contact fields plus sender config values. Supported
common fields include:

first_name, name, email, company, role, company_description, personalization,
focus_area, sender_name, sender_background, sender_project, sender_goal,
sender_links, bullet_points
"""

TEMPLATES = {
    "general": {
        "subject": "Quick note about {company}",
        "body": """Hi {first_name},

I came across {company} and was interested in your work around {focus_area}.

I'm {sender_name}, {sender_background}. I've been working on {sender_project}, and I thought there may be a useful overlap with what your team is building.

Relevant context:

{bullet_points}

I'd like to {sender_goal}. Would you be open to a quick call?

Best,
{sender_name}
{sender_links}""",
    },
    "concise": {
        "subject": "Quick question",
        "body": """Hi {first_name},

{personalization}

I'm {sender_name}. My background: {sender_background}.

I wanted to {sender_goal}. Open to a quick call?

Best,
{sender_name}
{sender_links}""",
    },
    "technical": {
        "subject": "Building around {focus_area}",
        "body": """Hi {first_name},

I noticed {company}'s work on {focus_area}. The technical direction looked relevant to things I've been building.

I'm {sender_name}, {sender_background}. Recent work:

{bullet_points}

I'd be interested in learning where your team could use help and whether there is a fit.

Best,
{sender_name}
{sender_links}""",
    },
    "referral": {
        "subject": "Best person to contact?",
        "body": """Hi {first_name},

I'm trying to reach the right person at {company} about {sender_goal}.

Short context: I'm {sender_name}, {sender_background}. Relevant work:

{bullet_points}

Could you point me to the best person to contact?

Best,
{sender_name}
{sender_links}""",
    },
    "follow_up": {
        "subject": "Following up",
        "body": """Hi {first_name},

Following up on my note about {company}. I still think there may be a useful overlap around {focus_area}.

Relevant context:

{bullet_points}

Would a quick call make sense?

Best,
{sender_name}
{sender_links}""",
    },
}
