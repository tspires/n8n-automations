# snippet: prospect_validator
"""
n8n Python Code Node: Prospect Validator (All-in-One)
Combines all validation checks into a single efficient pass.

Uses minimal HTTP requests by reusing page content across all checks.

Input: Expects items with 'url', 'website', 'company_url', or 'domain' field
Output: Consistent schema with {check}_passed, {check}_score, {check}_issues, {check}_data
"""

import re
import socket
import ssl
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

REQUEST_TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (compatible; ProspectValidator/1.0)"
HEADERS = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}

# Patterns
PARKED_PATTERNS = [
    r'buy\s+this\s+domain', r'domain\s+(is\s+)?for\s+sale', r'parked\s+(by|domain|free)',
    r'godaddy\.com/domain', r'sedo\.com', r'this\s+domain\s+(may\s+be|is)\s+for\s+sale',
]
CONSTRUCTION_PATTERNS = [r'under\s+construction', r'coming\s+soon', r'site\s+under\s+development']
TEMPLATE_PATTERNS = [r'lorem\s+ipsum', r'\[your\s+', r'just\s+another\s+wordpress\s+site']

TECH_PATTERNS = {
    "wordpress": r"wp-content|wordpress", "shopify": r"shopify|myshopify",
    "wix": r"wix\.com|wixsite", "react": r"_next/static|__next",
    "google_analytics": r"google-analytics|gtag", "hubspot": r"hubspot|hs-scripts",
    "stripe": r"stripe\.com|js\.stripe", "intercom": r"intercom|intercomcdn",
}

EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
PHONE_PATTERN = r'\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}'
INVALID_EMAIL_DOMAINS = ['example.com', 'sentry.io', 'wixpress.com', 'schema.org']

SOCIAL_PATTERNS = {
    "linkedin": r'linkedin\.com/(company|in)/[\w-]+',
    "twitter": r'(twitter\.com|x\.com)/\w+',
    "facebook": r'facebook\.com/[\w.]+',
}

BUSINESS_TOOLS = {'google_analytics', 'hubspot', 'intercom', 'stripe'}
MIN_WORD_COUNT = 50


def validate_prospect(url: str) -> dict:
    """Run all validation checks on a prospect URL."""

    result = {
        "url_checked": None,

        # Health
        "health_passed": False,
        "health_score": 0,
        "health_issues": [],
        "health_data": {"status_code": None, "response_time_ms": None},

        # Legitimacy
        "legitimacy_passed": False,
        "legitimacy_score": 0,
        "legitimacy_issues": [],
        "legitimacy_data": {"word_count": 0},

        # SEO
        "seo_passed": False,
        "seo_score": 0,
        "seo_issues": [],
        "seo_data": {"title": None, "has_https": False, "has_viewport": False},

        # Contactability
        "contactability_passed": False,
        "contactability_score": 0,
        "contactability_issues": [],
        "contactability_data": {"emails": [], "phones": [], "social_links": {}},

        # Maturity
        "maturity_passed": False,
        "maturity_score": 0,
        "maturity_issues": [],
        "maturity_data": {"has_ssl": False, "has_mx_records": False, "tech_stack": []},

        # Overall
        "overall_passed": False,
        "overall_score": 0,
    }

    if not url:
        result["health_issues"].append("No URL provided")
        return result

    # Normalize URL
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"
    result["url_checked"] = url

    parsed = urlparse(url)
    domain = parsed.netloc.replace('www.', '')

    # === SINGLE HTTP REQUEST ===
    try:
        start_time = time.time()
        response = requests.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True, headers=HEADERS)
        response_time_ms = int((time.time() - start_time) * 1000)

        # --- HEALTH ---
        result["health_data"]["status_code"] = response.status_code
        result["health_data"]["response_time_ms"] = response_time_ms

        if response.status_code >= 400:
            result["health_issues"].append(f"HTTP {response.status_code}")
            return result

        result["health_passed"] = True
        result["health_score"] = 100 if response_time_ms < 1000 else (75 if response_time_ms < 2000 else 50)

        content = response.text
        content_lower = content.lower()

        # --- LEGITIMACY ---
        visible_text = re.sub(r'<script[^>]*>.*?</script>', ' ', content, flags=re.DOTALL | re.IGNORECASE)
        visible_text = re.sub(r'<style[^>]*>.*?</style>', ' ', visible_text, flags=re.DOTALL | re.IGNORECASE)
        visible_text = re.sub(r'<[^>]+>', ' ', visible_text)
        word_count = len(re.sub(r'\s+', ' ', visible_text).split())
        result["legitimacy_data"]["word_count"] = word_count

        for pattern in PARKED_PATTERNS:
            if re.search(pattern, content_lower):
                result["legitimacy_issues"].append("Parked domain")
                break
        for pattern in CONSTRUCTION_PATTERNS:
            if re.search(pattern, content_lower):
                result["legitimacy_issues"].append("Under construction")
                break
        for pattern in TEMPLATE_PATTERNS:
            if re.search(pattern, content_lower):
                result["legitimacy_issues"].append("Placeholder content")
                break
        if word_count < MIN_WORD_COUNT:
            result["legitimacy_issues"].append("Low word count")

        result["legitimacy_score"] = max(0, 100 - len(result["legitimacy_issues"]) * 25)
        result["legitimacy_passed"] = len(result["legitimacy_issues"]) == 0

        # --- SEO ---
        seo_data = result["seo_data"]
        seo_data["has_https"] = response.url.startswith("https://")

        title_match = re.search(r'<title[^>]*>([^<]+)</title>', content, re.IGNORECASE)
        if title_match:
            seo_data["title"] = title_match.group(1).strip()
        else:
            result["seo_issues"].append("Missing title")

        seo_data["has_viewport"] = bool(re.search(r'<meta[^>]+name=["\']viewport["\']', content, re.IGNORECASE))
        if not seo_data["has_https"]:
            result["seo_issues"].append("Not using HTTPS")
        if not seo_data["has_viewport"]:
            result["seo_issues"].append("Missing viewport")

        seo_score = 0
        if seo_data["title"]:
            seo_score += 30
        if seo_data["has_https"]:
            seo_score += 30
        if seo_data["has_viewport"]:
            seo_score += 20
        if re.search(r'<h1[^>]*>.*?</h1>', content, re.IGNORECASE | re.DOTALL):
            seo_score += 20

        result["seo_score"] = min(100, seo_score)
        result["seo_passed"] = result["seo_score"] >= 50 and seo_data["title"] and seo_data["has_https"]

        # --- CONTACTABILITY ---
        emails = list(set(re.findall(EMAIL_PATTERN, content)))
        emails = [e.lower() for e in emails if not any(d in e.lower() for d in INVALID_EMAIL_DOMAINS)][:10]
        phones = list(set(re.findall(PHONE_PATTERN, content)))[:5]

        social = {}
        for platform, pattern in SOCIAL_PATTERNS.items():
            match = re.search(r'https?://(?:www\.)?' + pattern, content, re.IGNORECASE)
            if match:
                social[platform] = match.group(0)

        result["contactability_data"]["emails"] = emails
        result["contactability_data"]["phones"] = phones
        result["contactability_data"]["social_links"] = social

        contact_score = 0
        if emails:
            contact_score += 40
        if phones:
            contact_score += 30
        if social:
            contact_score += min(20, len(social) * 7)
        if "linkedin" in social:
            contact_score += 10

        result["contactability_score"] = min(100, contact_score)
        result["contactability_passed"] = bool(emails) or bool(phones)
        if not result["contactability_passed"]:
            result["contactability_issues"].append("No email or phone found")

        # --- MATURITY (tech stack from content) ---
        tech_stack = []
        for tech, pattern in TECH_PATTERNS.items():
            if re.search(pattern, content_lower):
                tech_stack.append(tech)

        server = response.headers.get('Server', '').lower()
        if 'cloudflare' in server:
            tech_stack.append('cloudflare')

        result["maturity_data"]["tech_stack"] = list(set(tech_stack))

    except requests.exceptions.Timeout:
        result["health_issues"].append("Timeout")
        return result
    except requests.exceptions.SSLError:
        result["health_issues"].append("SSL Error")
        return result
    except requests.exceptions.ConnectionError:
        result["health_issues"].append("Connection Failed")
        return result
    except Exception as e:
        result["health_issues"].append(f"Error: {str(e)[:50]}")
        return result

    # === ADDITIONAL CHECKS (SSL, MX) ===
    maturity_score = 0

    # SSL check
    try:
        context = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=3) as sock:
            with context.wrap_socket(sock, server_hostname=domain):
                result["maturity_data"]["has_ssl"] = True
                maturity_score += 25
    except Exception:
        result["maturity_issues"].append("No SSL certificate")

    # MX records
    try:
        import dns.resolver
        if dns.resolver.resolve(domain, 'MX'):
            result["maturity_data"]["has_mx_records"] = True
            maturity_score += 25
    except Exception:
        pass

    # Tech stack bonus
    if result["maturity_data"]["tech_stack"]:
        maturity_score += min(25, len(result["maturity_data"]["tech_stack"]) * 5)
    if set(result["maturity_data"]["tech_stack"]) & BUSINESS_TOOLS:
        maturity_score += 15

    result["maturity_score"] = min(100, maturity_score)
    result["maturity_passed"] = maturity_score >= 40 and result["maturity_data"]["has_ssl"]

    # === OVERALL ===
    overall = (
        result["health_score"] * 0.10 +
        result["legitimacy_score"] * 0.25 +
        result["seo_score"] * 0.15 +
        result["contactability_score"] * 0.30 +
        result["maturity_score"] * 0.20
    )
    result["overall_score"] = round(overall)
    result["overall_passed"] = (
        result["health_passed"] and
        result["legitimacy_passed"] and
        result["contactability_passed"] and
        result["overall_score"] >= 50
    )

    return result


# --- n8n Code Node Entry Point ---
output = []

for item in _input.all():
    data = item.json
    url = data.get("url_checked") or data.get("url") or data.get("website") or data.get("company_url") or data.get("domain")

    check_result = validate_prospect(url)
    output.append({**data, **check_result})

return output
