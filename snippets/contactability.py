# snippet: contactability
"""
n8n Python Code Node: Contactability Check
Extracts contact information and social presence from company websites.

Input: Expects items with 'url' field (or url_checked from previous step)
Output: contactability_passed, contactability_score, contactability_issues, contactability_data
"""

import re
from urllib.parse import urljoin

import requests

REQUEST_TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (compatible; ProspectValidator/1.0)"

EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
PHONE_PATTERN = r'\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}'

SOCIAL_PATTERNS = {
    "linkedin": r'linkedin\.com/(company|in)/[\w-]+',
    "twitter": r'(twitter\.com|x\.com)/\w+',
    "facebook": r'facebook\.com/[\w.]+',
    "instagram": r'instagram\.com/[\w_.]+',
    "youtube": r'youtube\.com/(channel|c|user|@)[\w-]+',
    "github": r'github\.com/[\w-]+',
}

CONTACT_PATHS = ['/contact', '/about', '/get-in-touch', '/reach-us']

INVALID_EMAIL_DOMAINS = [
    'example.com', 'email.com', 'domain.com', 'sentry.io',
    'wixpress.com', 'squarespace.com', 'wordpress.com', 'schema.org',
]


def extract_emails(content: str) -> list:
    """Extract valid email addresses."""
    emails = re.findall(EMAIL_PATTERN, content)
    valid = [e.lower() for e in emails if not any(d in e.lower() for d in INVALID_EMAIL_DOMAINS)]
    return list(set(valid))[:10]


def extract_phones(content: str) -> list:
    """Extract phone numbers."""
    phones = re.findall(PHONE_PATTERN, content)
    cleaned = [p.strip() for p in phones if len(re.sub(r'[^\d]', '', p)) >= 10]
    return list(set(cleaned))[:5]


def extract_social(content: str) -> dict:
    """Extract social media links."""
    social = {}
    for platform, pattern in SOCIAL_PATTERNS.items():
        match = re.search(r'https?://(?:www\.)?' + pattern, content, re.IGNORECASE)
        if match:
            social[platform] = match.group(0)
    return social


def find_contact_page(base_url: str, content: str) -> str:
    """Find contact page URL."""
    # Look for contact links
    link_match = re.search(r'href=["\']([^"\']*contact[^"\']*)["\']', content, re.IGNORECASE)
    if link_match:
        href = link_match.group(1)
        if href.startswith('http'):
            return href
        return urljoin(base_url, href)

    # Try common paths
    headers = {"User-Agent": USER_AGENT}
    for path in CONTACT_PATHS:
        try:
            url = urljoin(base_url, path)
            resp = requests.head(url, timeout=3, allow_redirects=True, headers=headers)
            if resp.status_code == 200:
                return url
        except Exception:
            pass
    return None


def check_contactability(url: str) -> dict:
    """Extract contact information from a website."""
    result = {
        "contactability_passed": False,
        "contactability_score": 0,
        "contactability_issues": [],
        "contactability_data": {
            "emails": [],
            "phones": [],
            "social_links": {},
            "contact_page_url": None,
            "has_contact_page": False,
        },
    }

    if not url:
        result["contactability_issues"].append("No URL provided")
        return result

    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"

    headers = {"User-Agent": USER_AGENT}

    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True, headers=headers)
        content = response.text
        data = result["contactability_data"]

        # Extract from main page
        data["emails"] = extract_emails(content)
        data["phones"] = extract_phones(content)
        data["social_links"] = extract_social(content)

        # Find and scrape contact page
        contact_page = find_contact_page(url, content)
        if contact_page:
            data["contact_page_url"] = contact_page
            data["has_contact_page"] = True

            try:
                contact_resp = requests.get(contact_page, timeout=REQUEST_TIMEOUT, headers=headers)
                contact_content = contact_resp.text
                data["emails"] = list(set(data["emails"] + extract_emails(contact_content)))[:10]
                data["phones"] = list(set(data["phones"] + extract_phones(contact_content)))[:5]
                data["social_links"].update(extract_social(contact_content))
            except Exception:
                pass

        # Calculate score
        score = 0
        if data["emails"]:
            score += 35
        if data["phones"]:
            score += 25
        if data["social_links"]:
            score += min(20, len(data["social_links"]) * 5)
        if "linkedin" in data["social_links"]:
            score += 10
        if data["has_contact_page"]:
            score += 10

        result["contactability_score"] = min(100, score)
        result["contactability_passed"] = bool(data["emails"]) or bool(data["phones"])

        if not result["contactability_passed"]:
            result["contactability_issues"].append("No email or phone found")

    except requests.exceptions.Timeout:
        result["contactability_issues"].append("Timeout")
    except requests.exceptions.ConnectionError:
        result["contactability_issues"].append("Connection Failed")
    except Exception as e:
        result["contactability_issues"].append(f"Error: {str(e)[:50]}")

    return result


# --- n8n Code Node Entry Point ---
output = []

for item in _input.all():
    data = item.json
    url = data.get("url_checked") or data.get("url") or data.get("website") or data.get("domain")

    check_result = check_contactability(url)
    output.append({**data, **check_result})

return output
