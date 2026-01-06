# snippet: company_maturity
"""
n8n Python Code Node: Company Maturity Check
Analyzes domain age, DNS records, and technology signals.

Input: Expects items with 'url' field (or url_checked from previous step)
Output: Adds 'domain_age_days', 'has_mx_records', 'tech_signals', 'ssl_info'
"""

import re
import socket
import ssl
from datetime import datetime
from urllib.parse import urlparse

import requests

REQUEST_TIMEOUT = 10

# Technology detection patterns (header-based and content-based)
TECH_PATTERNS = {
    # From headers
    "nginx": (r"nginx", "server"),
    "apache": (r"apache", "server"),
    "cloudflare": (r"cloudflare", "server"),
    "iis": (r"microsoft-iis", "server"),
    # From content/headers
    "wordpress": (r"wp-content|wordpress", "content"),
    "shopify": (r"shopify|myshopify", "content"),
    "wix": (r"wix\.com|wixsite", "content"),
    "squarespace": (r"squarespace", "content"),
    "webflow": (r"webflow", "content"),
    "drupal": (r"drupal|sites/default/files", "content"),
    "magento": (r"magento|mage/", "content"),
    "react": (r"react|_next/static|__next", "content"),
    "vue": (r"vue\.js|vue\.min\.js", "content"),
    "angular": (r"angular|ng-version", "content"),
    "bootstrap": (r"bootstrap\.min\.(css|js)", "content"),
    "jquery": (r"jquery\.min\.js|jquery-\d", "content"),
    "google_analytics": (r"google-analytics|gtag|ga\.js", "content"),
    "google_tag_manager": (r"googletagmanager", "content"),
    "hubspot": (r"hubspot|hs-scripts", "content"),
    "intercom": (r"intercom|intercomcdn", "content"),
    "zendesk": (r"zendesk|zdassets", "content"),
    "stripe": (r"stripe\.com|js\.stripe", "content"),
}


def get_domain_from_url(url: str) -> str:
    """Extract domain from URL."""
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"
    parsed = urlparse(url)
    return parsed.netloc.replace('www.', '')


def check_mx_records(domain: str) -> bool:
    """Check if domain has MX records (email capability)."""
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, 'MX')
        return len(answers) > 0
    except Exception:
        # Fallback: try nslookup-style check
        try:
            socket.getaddrinfo(f"mail.{domain}", 25)
            return True
        except Exception:
            pass
    return False


def get_ssl_info(domain: str) -> dict:
    """Get SSL certificate information."""
    ssl_info = {
        "has_ssl": False,
        "ssl_issuer": None,
        "ssl_expiry_days": None,
    }

    try:
        context = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                ssl_info["has_ssl"] = True

                # Get issuer
                issuer = dict(x[0] for x in cert.get('issuer', []))
                ssl_info["ssl_issuer"] = issuer.get('organizationName', issuer.get('commonName', 'Unknown'))

                # Get expiry
                expiry_str = cert.get('notAfter')
                if expiry_str:
                    expiry = datetime.strptime(expiry_str, '%b %d %H:%M:%S %Y %Z')
                    days_until_expiry = (expiry - datetime.utcnow()).days
                    ssl_info["ssl_expiry_days"] = days_until_expiry

    except Exception:
        pass

    return ssl_info


def detect_technologies(headers: dict, content: str) -> list:
    """Detect technologies from headers and page content."""
    detected = []
    content_lower = content.lower()
    headers_lower = {k.lower(): v.lower() for k, v in headers.items()}

    for tech, (pattern, source) in TECH_PATTERNS.items():
        if source == "server":
            server_header = headers_lower.get('server', '')
            if re.search(pattern, server_header, re.IGNORECASE):
                detected.append(tech)
        elif source == "content":
            if re.search(pattern, content_lower, re.IGNORECASE):
                detected.append(tech)

    # Check X-Powered-By header
    powered_by = headers_lower.get('x-powered-by', '')
    if powered_by:
        if 'php' in powered_by:
            detected.append('php')
        if 'asp.net' in powered_by:
            detected.append('asp.net')
        if 'express' in powered_by:
            detected.append('express')

    return list(set(detected))


def check_maturity(url: str) -> dict:
    """Analyze company/domain maturity signals."""
    result = {
        "domain_age_days": None,
        "has_mx_records": False,
        "tech_stack": [],
        "has_ssl": False,
        "ssl_issuer": None,
        "ssl_expiry_days": None,
        "maturity_score": 0,
    }

    if not url:
        return result

    domain = get_domain_from_url(url)
    if not domain:
        return result

    # Normalize URL
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"

    # Check MX records
    result["has_mx_records"] = check_mx_records(domain)

    # Get SSL info
    ssl_info = get_ssl_info(domain)
    result.update(ssl_info)

    # Fetch page for technology detection
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ProspectValidator/1.0)"}
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True, headers=headers)
        result["tech_stack"] = detect_technologies(dict(response.headers), response.text)
    except Exception:
        pass

    # Try to get domain age via WHOIS (if python-whois is available)
    try:
        import whois
        w = whois.whois(domain)
        creation_date = w.creation_date
        if isinstance(creation_date, list):
            creation_date = creation_date[0]
        if creation_date:
            age_days = (datetime.now() - creation_date).days
            result["domain_age_days"] = age_days
    except Exception:
        pass

    # Calculate maturity score (0-100)
    score = 0

    # Domain age scoring
    if result["domain_age_days"]:
        if result["domain_age_days"] > 365 * 5:  # 5+ years
            score += 30
        elif result["domain_age_days"] > 365 * 2:  # 2+ years
            score += 20
        elif result["domain_age_days"] > 365:  # 1+ year
            score += 10
        elif result["domain_age_days"] > 180:  # 6+ months
            score += 5

    # MX records = has email infrastructure
    if result["has_mx_records"]:
        score += 20

    # SSL certificate
    if result["has_ssl"]:
        score += 15
        # Bonus for non-free SSL issuers (indicates investment)
        if result["ssl_issuer"] and "let's encrypt" not in result["ssl_issuer"].lower():
            score += 5

    # Technology stack = active development
    tech_count = len(result["tech_stack"])
    if tech_count > 0:
        score += min(20, tech_count * 5)

    # Business tools bonus (analytics, chat, payments)
    business_tools = {'google_analytics', 'google_tag_manager', 'hubspot', 'intercom', 'zendesk', 'stripe'}
    if set(result["tech_stack"]) & business_tools:
        score += 10

    result["maturity_score"] = min(100, score)

    return result


# --- n8n Code Node Entry Point ---
output = []

for item in _input.all():
    data = item.json

    url = data.get("url_checked") or data.get("url") or data.get("website") or data.get("domain")

    check_result = check_maturity(url)
    output.append({**data, **check_result})

return output
