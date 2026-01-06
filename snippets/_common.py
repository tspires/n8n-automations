"""
Shared utilities for n8n prospect validation snippets.
Import this module in other snippets to reduce duplication.
"""

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

# === CONSTANTS ===

REQUEST_TIMEOUT = 10
REQUEST_TIMEOUT_SHORT = 3
USER_AGENT = "Mozilla/5.0 (compatible; ProspectValidator/1.0)"

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
}

# Common URL field names to check
URL_FIELDS = ("url_checked", "url", "website", "company_url", "domain")


# === URL UTILITIES ===

def normalize_url(url: str) -> str:
    """Add https:// scheme if missing."""
    if not url:
        return url
    if not url.startswith(('http://', 'https://')):
        return f"https://{url}"
    return url


def extract_domain(url: str) -> str:
    """Extract domain from URL, stripping www prefix."""
    url = normalize_url(url)
    if not url:
        return ""
    parsed = urlparse(url)
    return parsed.netloc.replace('www.', '')


def get_url_from_item(data: dict) -> str:
    """Extract URL from item data, checking common field names."""
    for field in URL_FIELDS:
        if data.get(field):
            return data[field]
    return None


def is_valid_url(url: str) -> bool:
    """Basic URL format validation."""
    if not url:
        return False
    url = normalize_url(url)
    try:
        parsed = urlparse(url)
        return all([parsed.scheme, parsed.netloc, '.' in parsed.netloc])
    except Exception:
        return False


# === HTTP UTILITIES ===

def fetch_url(url: str, timeout: int = REQUEST_TIMEOUT, method: str = "GET") -> dict:
    """
    Fetch a URL with standard headers and error handling.
    Returns dict with 'response', 'error', 'response_time_ms'.
    """
    result = {
        "response": None,
        "error": None,
        "response_time_ms": None,
    }

    url = normalize_url(url)
    if not url:
        result["error"] = "No URL provided"
        return result

    import time
    start_time = time.time()

    try:
        if method.upper() == "HEAD":
            response = requests.head(url, timeout=timeout, allow_redirects=True, headers=DEFAULT_HEADERS)
            # Fallback to GET if HEAD blocked
            if response.status_code == 405:
                response = requests.get(url, timeout=timeout, allow_redirects=True, headers=DEFAULT_HEADERS)
        else:
            response = requests.get(url, timeout=timeout, allow_redirects=True, headers=DEFAULT_HEADERS)

        result["response"] = response
        result["response_time_ms"] = int((time.time() - start_time) * 1000)

    except requests.exceptions.Timeout:
        result["error"] = "Timeout"
    except requests.exceptions.SSLError:
        result["error"] = "SSL Error"
    except requests.exceptions.ConnectionError:
        result["error"] = "Connection Failed"
    except requests.exceptions.TooManyRedirects:
        result["error"] = "Too Many Redirects"
    except Exception as e:
        result["error"] = str(e)[:100]

    return result


def check_url_exists(url: str, timeout: int = REQUEST_TIMEOUT_SHORT) -> bool:
    """Quick check if URL returns 200."""
    try:
        response = requests.head(url, timeout=timeout, allow_redirects=True, headers=DEFAULT_HEADERS)
        return response.status_code == 200
    except Exception:
        return False


# === TEXT UTILITIES ===

def strip_html_tags(html: str) -> str:
    """Remove HTML tags from content."""
    text = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', ' ', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def get_utc_now() -> datetime:
    """Get current UTC time (non-deprecated method)."""
    return datetime.now(timezone.utc)
