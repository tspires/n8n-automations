# snippet: site_seo_check
"""
n8n Python Code Node: Site SEO Check
Analyzes on-page SEO factors and performance indicators to gauge business strength.

Input: Expects items with 'url' field (or url_checked from previous step)
Output: Adds 'seo_score', 'seo_passed', 'seo_issues', 'seo_signals'
"""

import re
import time
from urllib.parse import urlparse

import requests

REQUEST_TIMEOUT = 15
IDEAL_TITLE_LENGTH = (30, 60)
IDEAL_DESC_LENGTH = (120, 160)
MAX_PAGE_SIZE_KB = 3000  # 3MB is concerning
SLOW_RESPONSE_MS = 3000  # 3 seconds is slow


def check_seo(url: str) -> dict:
    """Analyze SEO factors for a website."""
    result = {
        "seo_score": 0,
        "seo_passed": False,
        "seo_issues": [],
        "seo_signals": {
            "has_title": False,
            "has_meta_description": False,
            "has_h1": False,
            "has_og_tags": False,
            "has_canonical": False,
            "has_viewport": False,
            "has_robots_txt": False,
            "has_sitemap": False,
            "has_structured_data": False,
            "has_https": False,
            "has_compression": False,
            "images_with_alt": 0,
            "images_without_alt": 0,
        },
        "seo_meta": {
            "title": None,
            "title_length": 0,
            "description": None,
            "description_length": 0,
            "h1_count": 0,
            "h1_text": None,
        },
        "seo_performance": {
            "response_time_ms": None,
            "page_size_kb": None,
            "uses_gzip": False,
        },
    }

    if not url:
        result["seo_issues"].append("No URL provided")
        return result

    # Normalize URL
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"

    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ProspectValidator/1.0)",
        "Accept-Encoding": "gzip, deflate",
    }

    try:
        # Measure response time
        start_time = time.time()
        response = requests.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True, headers=headers)
        response_time_ms = int((time.time() - start_time) * 1000)

        result["seo_performance"]["response_time_ms"] = response_time_ms

        if response_time_ms > SLOW_RESPONSE_MS:
            result["seo_issues"].append(f"Slow response: {response_time_ms}ms")

        # Check HTTPS
        result["seo_signals"]["has_https"] = response.url.startswith("https://")
        if not result["seo_signals"]["has_https"]:
            result["seo_issues"].append("Not using HTTPS")

        # Check compression
        content_encoding = response.headers.get("Content-Encoding", "")
        result["seo_signals"]["has_compression"] = "gzip" in content_encoding or "br" in content_encoding
        result["seo_performance"]["uses_gzip"] = result["seo_signals"]["has_compression"]

        # Page size
        page_size_kb = len(response.content) / 1024
        result["seo_performance"]["page_size_kb"] = round(page_size_kb, 1)
        if page_size_kb > MAX_PAGE_SIZE_KB:
            result["seo_issues"].append(f"Large page size: {round(page_size_kb)}KB")

        content = response.text
        content_lower = content.lower()

        # === META TAGS ===

        # Title tag
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', content, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).strip()
            result["seo_signals"]["has_title"] = True
            result["seo_meta"]["title"] = title
            result["seo_meta"]["title_length"] = len(title)

            if len(title) < IDEAL_TITLE_LENGTH[0]:
                result["seo_issues"].append("Title too short")
            elif len(title) > IDEAL_TITLE_LENGTH[1]:
                result["seo_issues"].append("Title too long")
        else:
            result["seo_issues"].append("Missing title tag")

        # Meta description
        desc_match = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', content, re.IGNORECASE)
        if not desc_match:
            desc_match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']', content, re.IGNORECASE)

        if desc_match:
            desc = desc_match.group(1).strip()
            result["seo_signals"]["has_meta_description"] = True
            result["seo_meta"]["description"] = desc
            result["seo_meta"]["description_length"] = len(desc)

            if len(desc) < IDEAL_DESC_LENGTH[0]:
                result["seo_issues"].append("Meta description too short")
            elif len(desc) > IDEAL_DESC_LENGTH[1]:
                result["seo_issues"].append("Meta description too long")
        else:
            result["seo_issues"].append("Missing meta description")

        # H1 tags (handle nested elements)
        h1_matches = re.findall(r'<h1[^>]*>(.*?)</h1>', content, re.IGNORECASE | re.DOTALL)
        h1_matches = [re.sub(r'<[^>]+>', '', h).strip() for h in h1_matches]  # Strip inner tags
        h1_matches = [h for h in h1_matches if h]  # Remove empty
        result["seo_meta"]["h1_count"] = len(h1_matches)
        if h1_matches:
            result["seo_signals"]["has_h1"] = True
            result["seo_meta"]["h1_text"] = h1_matches[0].strip()[:100]
            if len(h1_matches) > 1:
                result["seo_issues"].append(f"Multiple H1 tags ({len(h1_matches)})")
        else:
            result["seo_issues"].append("Missing H1 tag")

        # Open Graph tags
        og_match = re.search(r'<meta[^>]+property=["\']og:', content, re.IGNORECASE)
        result["seo_signals"]["has_og_tags"] = bool(og_match)
        if not og_match:
            result["seo_issues"].append("Missing Open Graph tags")

        # Canonical URL
        canonical_match = re.search(r'<link[^>]+rel=["\']canonical["\']', content, re.IGNORECASE)
        result["seo_signals"]["has_canonical"] = bool(canonical_match)

        # Viewport (mobile-friendly)
        viewport_match = re.search(r'<meta[^>]+name=["\']viewport["\']', content, re.IGNORECASE)
        result["seo_signals"]["has_viewport"] = bool(viewport_match)
        if not viewport_match:
            result["seo_issues"].append("Missing viewport meta (not mobile-friendly)")

        # Structured data (JSON-LD)
        jsonld_match = re.search(r'<script[^>]+type=["\']application/ld\+json["\']', content, re.IGNORECASE)
        result["seo_signals"]["has_structured_data"] = bool(jsonld_match)

        # Image alt tags
        images = re.findall(r'<img[^>]+>', content, re.IGNORECASE)
        images_with_alt = sum(1 for img in images if re.search(r'alt=["\'][^"\']+["\']', img, re.IGNORECASE))
        images_without_alt = len(images) - images_with_alt
        result["seo_signals"]["images_with_alt"] = images_with_alt
        result["seo_signals"]["images_without_alt"] = images_without_alt

        if images_without_alt > 3:
            result["seo_issues"].append(f"{images_without_alt} images missing alt text")

        # === CRAWLABILITY ===

        # Check robots.txt
        try:
            robots_resp = requests.head(f"{base_url}/robots.txt", timeout=3, headers=headers)
            result["seo_signals"]["has_robots_txt"] = robots_resp.status_code == 200
        except Exception:
            pass

        # Check sitemap
        try:
            sitemap_resp = requests.head(f"{base_url}/sitemap.xml", timeout=3, headers=headers)
            result["seo_signals"]["has_sitemap"] = sitemap_resp.status_code == 200
        except Exception:
            pass

    except requests.exceptions.Timeout:
        result["seo_issues"].append("Request timeout")
        return result
    except requests.exceptions.ConnectionError:
        result["seo_issues"].append("Connection failed")
        return result
    except Exception as e:
        result["seo_issues"].append(f"Error: {str(e)[:50]}")
        return result

    # === CALCULATE SCORE ===
    score = 0
    signals = result["seo_signals"]

    # Core SEO (50 points)
    if signals["has_title"]:
        score += 10
    if signals["has_meta_description"]:
        score += 10
    if signals["has_h1"]:
        score += 10
    if signals["has_https"]:
        score += 10
    if signals["has_viewport"]:
        score += 10

    # Good practices (30 points)
    if signals["has_og_tags"]:
        score += 5
    if signals["has_canonical"]:
        score += 5
    if signals["has_structured_data"]:
        score += 10
    if signals["has_robots_txt"]:
        score += 5
    if signals["has_sitemap"]:
        score += 5

    # Performance (20 points)
    if signals["has_compression"]:
        score += 5
    if result["seo_performance"]["response_time_ms"] and result["seo_performance"]["response_time_ms"] < 1000:
        score += 10
    elif result["seo_performance"]["response_time_ms"] and result["seo_performance"]["response_time_ms"] < 2000:
        score += 5
    if result["seo_performance"]["page_size_kb"] and result["seo_performance"]["page_size_kb"] < 1000:
        score += 5

    # Deductions for issues
    score -= min(20, len(result["seo_issues"]) * 3)

    result["seo_score"] = max(0, min(100, score))
    result["seo_passed"] = result["seo_score"] >= 50 and signals["has_title"] and signals["has_https"]

    return result


# --- n8n Code Node Entry Point ---
output = []

for item in _input.all():
    data = item.json

    url = data.get("url_checked") or data.get("url") or data.get("website") or data.get("domain")

    check_result = check_seo(url)
    output.append({**data, **check_result})

return output
