# snippet: company_maturity
"""
n8n Python Code Node: Company Maturity Check
Analyzes domain age, DNS records, and technology signals.

Input: Expects items with 'url' field (or url_checked from previous step)
Output: maturity_passed, maturity_score, maturity_issues, maturity_data
"""

import re
import socket
import ssl
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

REQUEST_TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (compatible; ProspectValidator/1.0)"

TECH_PATTERNS = {
    "wordpress": r"wp-content|wordpress", "shopify": r"shopify|myshopify",
    "wix": r"wix\.com|wixsite", "squarespace": r"squarespace", "webflow": r"webflow",
    "drupal": r"drupal|sites/default/files", "magento": r"magento|mage/",
    "react": r"react|_next/static|__next", "vue": r"vue\.js|vue\.min\.js",
    "angular": r"angular|ng-version", "google_analytics": r"google-analytics|gtag|ga\.js",
    "google_tag_manager": r"googletagmanager", "hubspot": r"hubspot|hs-scripts",
    "intercom": r"intercom|intercomcdn", "zendesk": r"zendesk|zdassets",
    "stripe": r"stripe\.com|js\.stripe",
}

BUSINESS_TOOLS = {'google_analytics', 'google_tag_manager', 'hubspot', 'intercom', 'zendesk', 'stripe'}


def get_domain(url: str) -> str:
    """Extract domain from URL."""
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"
    return urlparse(url).netloc.replace('www.', '')


def check_mx_records(domain: str) -> bool:
    """Check if domain has MX records."""
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, 'MX')
        return len(answers) > 0
    except Exception:
        try:
            socket.getaddrinfo(f"mail.{domain}", 25)
            return True
        except Exception:
            pass
    return False


def get_ssl_info(domain: str) -> dict:
    """Get SSL certificate information."""
    info = {"has_ssl": False, "issuer": None, "expiry_days": None}
    try:
        context = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                info["has_ssl"] = True
                issuer = dict(x[0] for x in cert.get('issuer', []))
                info["issuer"] = issuer.get('organizationName', issuer.get('commonName', 'Unknown'))
                expiry_str = cert.get('notAfter')
                if expiry_str:
                    expiry = datetime.strptime(expiry_str, '%b %d %H:%M:%S %Y %Z')
                    info["expiry_days"] = (expiry.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).days
    except Exception:
        pass
    return info


def detect_tech(headers: dict, content: str) -> list:
    """Detect technologies from headers and content."""
    detected = []
    content_lower = content.lower()
    headers_lower = {k.lower(): v.lower() for k, v in headers.items()}

    for tech, pattern in TECH_PATTERNS.items():
        if re.search(pattern, content_lower, re.IGNORECASE):
            detected.append(tech)

    server = headers_lower.get('server', '')
    if 'nginx' in server:
        detected.append('nginx')
    elif 'apache' in server:
        detected.append('apache')
    elif 'cloudflare' in server:
        detected.append('cloudflare')

    powered_by = headers_lower.get('x-powered-by', '')
    if 'php' in powered_by:
        detected.append('php')
    if 'express' in powered_by:
        detected.append('express')

    return list(set(detected))


def check_maturity(url: str) -> dict:
    """Analyze company/domain maturity signals."""
    result = {
        "maturity_passed": False,
        "maturity_score": 0,
        "maturity_issues": [],
        "maturity_data": {
            "domain_age_days": None,
            "has_mx_records": False,
            "has_ssl": False,
            "ssl_issuer": None,
            "ssl_expiry_days": None,
            "tech_stack": [],
            "has_business_tools": False,
        },
    }

    if not url:
        result["maturity_issues"].append("No URL provided")
        return result

    domain = get_domain(url)
    if not domain:
        result["maturity_issues"].append("Invalid URL")
        return result

    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"

    # Check MX records
    result["maturity_data"]["has_mx_records"] = check_mx_records(domain)

    # Get SSL info
    ssl_info = get_ssl_info(domain)
    result["maturity_data"]["has_ssl"] = ssl_info["has_ssl"]
    result["maturity_data"]["ssl_issuer"] = ssl_info["issuer"]
    result["maturity_data"]["ssl_expiry_days"] = ssl_info["expiry_days"]

    if not ssl_info["has_ssl"]:
        result["maturity_issues"].append("No SSL certificate")

    # Fetch page for tech detection
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True, headers=headers)
        tech_stack = detect_tech(dict(response.headers), response.text)
        result["maturity_data"]["tech_stack"] = tech_stack
        result["maturity_data"]["has_business_tools"] = bool(set(tech_stack) & BUSINESS_TOOLS)
    except Exception:
        result["maturity_issues"].append("Could not fetch page")

    # Domain age via WHOIS
    try:
        import whois
        w = whois.whois(domain)
        creation_date = w.creation_date
        if isinstance(creation_date, list):
            creation_date = creation_date[0]
        if creation_date:
            if creation_date.tzinfo is None:
                creation_date = creation_date.replace(tzinfo=timezone.utc)
            result["maturity_data"]["domain_age_days"] = (datetime.now(timezone.utc) - creation_date).days
    except Exception:
        pass

    # Calculate score
    score = 0
    data = result["maturity_data"]

    if data["domain_age_days"]:
        if data["domain_age_days"] > 365 * 5:
            score += 30
        elif data["domain_age_days"] > 365 * 2:
            score += 20
        elif data["domain_age_days"] > 365:
            score += 10

    if data["has_mx_records"]:
        score += 20
    if data["has_ssl"]:
        score += 20
    if data["tech_stack"]:
        score += min(15, len(data["tech_stack"]) * 3)
    if data["has_business_tools"]:
        score += 15

    result["maturity_score"] = min(100, score)
    result["maturity_passed"] = result["maturity_score"] >= 40 and data["has_ssl"]

    return result


# --- n8n Code Node Entry Point ---
output = []

for item in _input.all():
    data = item.json
    url = data.get("url_checked") or data.get("url") or data.get("website") or data.get("domain")

    check_result = check_maturity(url)
    output.append({**data, **check_result})

return output
