# snippet: prospect_validator
"""
n8n Python Code Node: Prospect Validator (All-in-One)
Combines all validation checks into a single efficient pass.

Performs: URL health, business legitimacy, SEO, contactability, and maturity checks.
Uses minimal HTTP requests by reusing page content across all checks.

Input: Expects items with 'url', 'website', 'company_url', or 'domain' field
Output: Comprehensive validation results with overall_score and overall_passed
"""

import re
import socket
import ssl
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests

# === CONSTANTS ===

REQUEST_TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (compatible; ProspectValidator/1.0)"
HEADERS = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}

# Thresholds
MIN_WORD_COUNT = 50
SLOW_RESPONSE_MS = 3000

# === PATTERNS ===

PARKED_PATTERNS = [
    r'buy\s+this\s+domain', r'domain\s+(is\s+)?for\s+sale', r'parked\s+(by|domain|free)',
    r'godaddy\.com/domain', r'sedo\.com', r'afternic\.com', r'hugedomains\.com',
    r'this\s+domain\s+(may\s+be|is)\s+for\s+sale',
]

CONSTRUCTION_PATTERNS = [
    r'under\s+construction', r'coming\s+soon', r'launching\s+soon',
    r'check\s+back\s+(soon|later)', r'site\s+under\s+development',
]

TEMPLATE_PATTERNS = [
    r'lorem\s+ipsum', r'your\s+company\s+(name|slogan)', r'sample\s+text\s+here',
    r'\[your\s+', r'just\s+another\s+wordpress\s+site',
]

TECH_PATTERNS = {
    "wordpress": r"wp-content|wordpress", "shopify": r"shopify|myshopify",
    "wix": r"wix\.com|wixsite", "squarespace": r"squarespace", "webflow": r"webflow",
    "react": r"_next/static|__next", "google_analytics": r"google-analytics|gtag",
    "hubspot": r"hubspot|hs-scripts", "stripe": r"stripe\.com|js\.stripe",
    "intercom": r"intercom|intercomcdn", "zendesk": r"zendesk|zdassets",
}

EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
INVALID_EMAIL_DOMAINS = ['example.com', 'email.com', 'domain.com', 'sentry.io', 'wixpress.com', 'schema.org']

PHONE_PATTERN = r'\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}'

SOCIAL_PATTERNS = {
    "linkedin": r'linkedin\.com/(company|in)/[\w-]+',
    "twitter": r'(twitter\.com|x\.com)/\w+',
    "facebook": r'facebook\.com/[\w.]+',
}


def validate_prospect(url: str) -> dict:
    """Run all validation checks on a prospect URL."""

    result = {
        # Overall
        "overall_score": 0,
        "overall_passed": False,
        "issues": [],

        # URL Health
        "url_valid": False,
        "url_checked": None,
        "url_status_code": None,

        # Business Legitimacy
        "is_real_business": False,
        "legitimacy_score": 0,
        "word_count": 0,

        # SEO
        "seo_score": 0,
        "seo_passed": False,
        "has_title": False,
        "has_meta_description": False,
        "has_https": False,
        "response_time_ms": None,

        # Contactability
        "contactability_score": 0,
        "contactability_passed": False,
        "emails": [],
        "phones": [],
        "social_links": {},

        # Maturity
        "maturity_score": 0,
        "maturity_passed": False,
        "has_ssl": False,
        "has_mx_records": False,
        "tech_stack": [],
        "domain_age_days": None,
    }

    if not url:
        result["issues"].append("No URL provided")
        return result

    # Normalize URL
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"
    result["url_checked"] = url

    parsed = urlparse(url)
    domain = parsed.netloc.replace('www.', '')
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    # === SINGLE HTTP REQUEST FOR MAIN PAGE ===
    try:
        start_time = time.time()
        response = requests.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True, headers=HEADERS)
        response_time_ms = int((time.time() - start_time) * 1000)

        result["url_status_code"] = response.status_code
        result["url_valid"] = response.status_code < 400
        result["response_time_ms"] = response_time_ms
        result["has_https"] = response.url.startswith("https://")

        if not result["url_valid"]:
            result["issues"].append(f"HTTP error: {response.status_code}")
            return result

        if response_time_ms > SLOW_RESPONSE_MS:
            result["issues"].append(f"Slow response: {response_time_ms}ms")

        content = response.text
        content_lower = content.lower()

        # === LEGITIMACY CHECKS ===
        visible_text = re.sub(r'<script[^>]*>.*?</script>', ' ', content, flags=re.DOTALL | re.IGNORECASE)
        visible_text = re.sub(r'<style[^>]*>.*?</style>', ' ', visible_text, flags=re.DOTALL | re.IGNORECASE)
        visible_text = re.sub(r'<[^>]+>', ' ', visible_text)
        visible_text = re.sub(r'\s+', ' ', visible_text).strip()
        result["word_count"] = len(visible_text.split())

        red_flags = []
        for pattern in PARKED_PATTERNS:
            if re.search(pattern, content_lower):
                red_flags.append("Parked domain")
                break
        for pattern in CONSTRUCTION_PATTERNS:
            if re.search(pattern, content_lower):
                red_flags.append("Under construction")
                break
        for pattern in TEMPLATE_PATTERNS:
            if re.search(pattern, content_lower):
                red_flags.append("Placeholder content")
                break
        if result["word_count"] < MIN_WORD_COUNT:
            red_flags.append("Low word count")

        result["issues"].extend(red_flags)
        result["is_real_business"] = len(red_flags) == 0 and result["word_count"] >= MIN_WORD_COUNT
        result["legitimacy_score"] = max(0, 100 - len(red_flags) * 25)

        # === SEO CHECKS ===
        seo_score = 0

        title_match = re.search(r'<title[^>]*>([^<]+)</title>', content, re.IGNORECASE)
        if title_match:
            result["has_title"] = True
            seo_score += 15

        desc_match = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', content, re.IGNORECASE)
        if desc_match:
            result["has_meta_description"] = True
            seo_score += 15

        if result["has_https"]:
            seo_score += 20
        if re.search(r'<meta[^>]+name=["\']viewport["\']', content, re.IGNORECASE):
            seo_score += 10
        if re.search(r'<h1[^>]*>.*?</h1>', content, re.IGNORECASE | re.DOTALL):
            seo_score += 10
        if re.search(r'type=["\']application/ld\+json["\']', content, re.IGNORECASE):
            seo_score += 10
        if response_time_ms < 1000:
            seo_score += 10
        elif response_time_ms < 2000:
            seo_score += 5

        result["seo_score"] = min(100, seo_score)
        result["seo_passed"] = result["seo_score"] >= 50 and result["has_title"] and result["has_https"]

        # === CONTACTABILITY CHECKS ===
        emails = list(set(re.findall(EMAIL_PATTERN, content)))
        emails = [e.lower() for e in emails if not any(d in e.lower() for d in INVALID_EMAIL_DOMAINS)][:10]
        result["emails"] = emails

        phones = list(set(re.findall(PHONE_PATTERN, content)))[:5]
        result["phones"] = phones

        for platform, pattern in SOCIAL_PATTERNS.items():
            if re.search(pattern, content, re.IGNORECASE):
                match = re.search(r'https?://(?:www\.)?' + pattern, content, re.IGNORECASE)
                result["social_links"][platform] = match.group(0) if match else True

        contact_score = 0
        if emails:
            contact_score += 35
        if phones:
            contact_score += 25
        if result["social_links"]:
            contact_score += min(20, len(result["social_links"]) * 7)
        if "linkedin" in result["social_links"]:
            contact_score += 10

        result["contactability_score"] = min(100, contact_score)
        result["contactability_passed"] = bool(emails) or bool(phones)

        # === TECH STACK DETECTION ===
        tech_stack = []
        for tech, pattern in TECH_PATTERNS.items():
            if re.search(pattern, content_lower):
                tech_stack.append(tech)
        server = response.headers.get('Server', '').lower()
        if 'nginx' in server:
            tech_stack.append('nginx')
        elif 'apache' in server:
            tech_stack.append('apache')
        elif 'cloudflare' in server:
            tech_stack.append('cloudflare')
        result["tech_stack"] = list(set(tech_stack))

    except requests.exceptions.Timeout:
        result["issues"].append("Request timeout")
        return result
    except requests.exceptions.SSLError:
        result["issues"].append("SSL error")
        return result
    except requests.exceptions.ConnectionError:
        result["issues"].append("Connection failed")
        return result
    except Exception as e:
        result["issues"].append(f"Error: {str(e)[:50]}")
        return result

    # === MATURITY CHECKS (Additional requests) ===
    maturity_score = 0

    # SSL check
    try:
        context = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=3) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                result["has_ssl"] = True
                maturity_score += 20
    except Exception:
        pass

    # MX records check
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, 'MX')
        if answers:
            result["has_mx_records"] = True
            maturity_score += 20
    except Exception:
        pass

    # Tech stack bonus
    if result["tech_stack"]:
        maturity_score += min(20, len(result["tech_stack"]) * 5)

    # Business tools bonus
    business_tools = {'google_analytics', 'hubspot', 'intercom', 'zendesk', 'stripe'}
    if set(result["tech_stack"]) & business_tools:
        maturity_score += 15

    result["maturity_score"] = min(100, maturity_score)
    result["maturity_passed"] = result["maturity_score"] >= 40 and result["has_ssl"]

    # === OVERALL SCORE ===
    weights = {
        "legitimacy": 0.25,
        "seo": 0.20,
        "contactability": 0.30,
        "maturity": 0.25,
    }
    overall = (
        result["legitimacy_score"] * weights["legitimacy"] +
        result["seo_score"] * weights["seo"] +
        result["contactability_score"] * weights["contactability"] +
        result["maturity_score"] * weights["maturity"]
    )
    result["overall_score"] = round(overall)
    result["overall_passed"] = (
        result["url_valid"] and
        result["is_real_business"] and
        result["contactability_passed"] and
        result["overall_score"] >= 50
    )

    return result


# --- n8n Code Node Entry Point ---
output = []

for item in _input.all():
    data = item.json
    url = data.get("url_checked") or data.get("url") or data.get("website") or data.get("company_url") or data.get("domain")

    result = validate_prospect(url)
    output.append({**data, **result})

return output
