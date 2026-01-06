# snippet: contactability
"""
n8n Python Code Node: Contactability Check
Extracts contact information and social presence from company websites.

Input: Expects items with 'url' field (or url_checked from previous step)
Output: Adds 'emails', 'phones', 'social_links', 'has_contact_page', 'contactability_score'
"""

import re
from urllib.parse import urljoin, urlparse

import requests

REQUEST_TIMEOUT = 10

# Email pattern - captures most valid email formats
EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

# Phone patterns (US/International)
PHONE_PATTERNS = [
    r'\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}',  # US
    r'\+[0-9]{1,3}[-.\s]?[0-9]{1,4}[-.\s]?[0-9]{1,4}[-.\s]?[0-9]{1,9}',  # International
]

# Social media patterns
SOCIAL_PATTERNS = {
    "linkedin": r'linkedin\.com/(company|in)/[a-zA-Z0-9_-]+',
    "twitter": r'(twitter\.com|x\.com)/[a-zA-Z0-9_]+',
    "facebook": r'facebook\.com/[a-zA-Z0-9.]+',
    "instagram": r'instagram\.com/[a-zA-Z0-9_.]+',
    "youtube": r'youtube\.com/(channel|c|user|@)[a-zA-Z0-9_-]+',
    "github": r'github\.com/[a-zA-Z0-9_-]+',
}

# Contact page URL patterns
CONTACT_PAGE_PATTERNS = [
    r'/contact',
    r'/about',
    r'/get-in-touch',
    r'/reach-us',
    r'/connect',
]

# Email addresses to filter out (generic/invalid)
INVALID_EMAIL_PATTERNS = [
    r'example\.com',
    r'email\.com',
    r'domain\.com',
    r'yourcompany',
    r'sentry\.io',
    r'wixpress\.com',
    r'squarespace',
    r'wordpress',
    r'schema\.org',
]


def is_valid_email(email: str) -> bool:
    """Filter out invalid/placeholder emails."""
    email_lower = email.lower()
    for pattern in INVALID_EMAIL_PATTERNS:
        if re.search(pattern, email_lower):
            return False
    return True


def extract_emails(content: str) -> list:
    """Extract valid email addresses from content."""
    emails = re.findall(EMAIL_PATTERN, content)
    # Dedupe and filter
    valid_emails = list(set(e.lower() for e in emails if is_valid_email(e)))
    return valid_emails[:10]  # Limit to prevent huge lists


def extract_phones(content: str) -> list:
    """Extract phone numbers from content."""
    phones = []
    for pattern in PHONE_PATTERNS:
        matches = re.findall(pattern, content)
        phones.extend(matches)

    # Clean and dedupe
    cleaned = []
    for phone in phones:
        # Remove non-digit except leading +
        clean = re.sub(r'[^\d+]', '', phone)
        if len(clean) >= 10:  # Valid phone length
            cleaned.append(phone.strip())

    return list(set(cleaned))[:5]


def extract_social_links(content: str) -> dict:
    """Extract social media profile links."""
    social = {}
    for platform, pattern in SOCIAL_PATTERNS.items():
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            # Get the full URL match
            full_pattern = r'https?://(www\.)?' + pattern
            full_matches = re.findall(full_pattern, content, re.IGNORECASE)
            if full_matches:
                social[platform] = f"https://{platform}.com/{matches[0]}" if platform != "twitter" else f"https://x.com/{matches[0]}"
            else:
                social[platform] = True  # Found but couldn't extract full URL

    return social


def find_contact_page(base_url: str, content: str) -> str:
    """Try to find a contact page URL."""
    # Look for contact links in the page
    link_pattern = r'href=["\']([^"\']*(?:contact|about|get-in-touch)[^"\']*)["\']'
    matches = re.findall(link_pattern, content, re.IGNORECASE)

    for match in matches:
        if match.startswith('http'):
            return match
        elif match.startswith('/'):
            return urljoin(base_url, match)

    # Try common contact page paths
    for pattern in CONTACT_PAGE_PATTERNS:
        try:
            test_url = urljoin(base_url, pattern)
            response = requests.head(test_url, timeout=3, allow_redirects=True)
            if response.status_code == 200:
                return test_url
        except Exception:
            pass

    return None


def check_contactability(url: str) -> dict:
    """Extract contact information from a website."""
    result = {
        "emails": [],
        "phones": [],
        "social_links": {},
        "contact_page_url": None,
        "has_contact_page": False,
        "contactability_score": 0,
        "contactability_passed": False,
    }

    if not url:
        return result

    # Normalize URL
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"

    headers = {"User-Agent": "Mozilla/5.0 (compatible; ProspectValidator/1.0)"}

    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True, headers=headers)
        content = response.text

        # Extract from main page
        result["emails"] = extract_emails(content)
        result["phones"] = extract_phones(content)
        result["social_links"] = extract_social_links(content)

        # Try to find and scrape contact page
        contact_page = find_contact_page(url, content)
        if contact_page:
            result["contact_page_url"] = contact_page
            result["has_contact_page"] = True

            # Scrape contact page for more info
            try:
                contact_response = requests.get(contact_page, timeout=REQUEST_TIMEOUT, headers=headers)
                contact_content = contact_response.text

                # Merge findings
                result["emails"] = list(set(result["emails"] + extract_emails(contact_content)))[:10]
                result["phones"] = list(set(result["phones"] + extract_phones(contact_content)))[:5]

                # Merge social links
                new_social = extract_social_links(contact_content)
                result["social_links"].update(new_social)

            except Exception:
                pass

    except requests.exceptions.Timeout:
        pass
    except requests.exceptions.ConnectionError:
        pass
    except Exception:
        pass

    # Calculate contactability score (0-100)
    score = 0

    # Email is most valuable
    if result["emails"]:
        score += 30
        if len(result["emails"]) > 1:
            score += 10

    # Phone adds credibility
    if result["phones"]:
        score += 20

    # Contact page shows professionalism
    if result["has_contact_page"]:
        score += 15

    # Social presence
    social_count = len(result["social_links"])
    if social_count > 0:
        score += min(25, social_count * 5)

    # LinkedIn is especially valuable for B2B
    if "linkedin" in result["social_links"]:
        score += 10

    result["contactability_score"] = min(100, score)
    result["contactability_passed"] = bool(result["emails"]) or bool(result["phones"])

    return result


# --- n8n Code Node Entry Point ---
output = []

for item in _input.all():
    data = item.json

    url = data.get("url_checked") or data.get("url") or data.get("website") or data.get("domain")

    check_result = check_contactability(url)
    output.append({**data, **check_result})

return output
