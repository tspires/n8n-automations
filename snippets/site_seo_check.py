# snippet: site_seo_check
"""
n8n Python Code Node: Site SEO Check
Analyzes on-page SEO factors and performance indicators.

Input: Expects items with 'url' field (or url_checked from previous step)
Output: seo_passed, seo_score, seo_issues, seo_data
"""

import re
import time
from urllib.parse import urlparse

import requests

REQUEST_TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (compatible; ProspectValidator/1.0)"

IDEAL_TITLE_LENGTH = (30, 60)
IDEAL_DESC_LENGTH = (120, 160)


def check_seo(url: str) -> dict:
    """Analyze SEO factors for a website."""
    result = {
        "seo_passed": False,
        "seo_score": 0,
        "seo_issues": [],
        "seo_data": {
            "title": None,
            "title_length": 0,
            "description": None,
            "description_length": 0,
            "h1_text": None,
            "h1_count": 0,
            "has_https": False,
            "has_viewport": False,
            "has_og_tags": False,
            "has_canonical": False,
            "has_structured_data": False,
            "has_robots_txt": False,
            "has_sitemap": False,
            "has_compression": False,
            "response_time_ms": None,
            "page_size_kb": None,
            "images_without_alt": 0,
        },
    }

    if not url:
        result["seo_issues"].append("No URL provided")
        return result

    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"

    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}

    try:
        start_time = time.time()
        response = requests.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True, headers=headers)
        response_time_ms = int((time.time() - start_time) * 1000)

        data = result["seo_data"]
        data["response_time_ms"] = response_time_ms
        data["page_size_kb"] = round(len(response.content) / 1024, 1)
        data["has_https"] = response.url.startswith("https://")
        data["has_compression"] = "gzip" in response.headers.get("Content-Encoding", "") or "br" in response.headers.get("Content-Encoding", "")

        content = response.text

        # Title
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', content, re.IGNORECASE)
        if title_match:
            data["title"] = title_match.group(1).strip()
            data["title_length"] = len(data["title"])
            if data["title_length"] < IDEAL_TITLE_LENGTH[0]:
                result["seo_issues"].append("Title too short")
            elif data["title_length"] > IDEAL_TITLE_LENGTH[1]:
                result["seo_issues"].append("Title too long")
        else:
            result["seo_issues"].append("Missing title")

        # Meta description
        desc_match = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', content, re.IGNORECASE)
        if not desc_match:
            desc_match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']', content, re.IGNORECASE)
        if desc_match:
            data["description"] = desc_match.group(1).strip()
            data["description_length"] = len(data["description"])
            if data["description_length"] < IDEAL_DESC_LENGTH[0]:
                result["seo_issues"].append("Description too short")
            elif data["description_length"] > IDEAL_DESC_LENGTH[1]:
                result["seo_issues"].append("Description too long")
        else:
            result["seo_issues"].append("Missing meta description")

        # H1 (handle nested elements)
        h1_matches = re.findall(r'<h1[^>]*>(.*?)</h1>', content, re.IGNORECASE | re.DOTALL)
        h1_texts = [re.sub(r'<[^>]+>', '', h).strip() for h in h1_matches]
        h1_texts = [h for h in h1_texts if h]
        data["h1_count"] = len(h1_texts)
        if h1_texts:
            data["h1_text"] = h1_texts[0][:100]
            if len(h1_texts) > 1:
                result["seo_issues"].append(f"Multiple H1 tags ({len(h1_texts)})")
        else:
            result["seo_issues"].append("Missing H1")

        # Other signals
        data["has_viewport"] = bool(re.search(r'<meta[^>]+name=["\']viewport["\']', content, re.IGNORECASE))
        data["has_og_tags"] = bool(re.search(r'<meta[^>]+property=["\']og:', content, re.IGNORECASE))
        data["has_canonical"] = bool(re.search(r'<link[^>]+rel=["\']canonical["\']', content, re.IGNORECASE))
        data["has_structured_data"] = bool(re.search(r'type=["\']application/ld\+json["\']', content, re.IGNORECASE))

        if not data["has_https"]:
            result["seo_issues"].append("Not using HTTPS")
        if not data["has_viewport"]:
            result["seo_issues"].append("Missing viewport (not mobile-friendly)")

        # Image alt tags
        images = re.findall(r'<img[^>]+>', content, re.IGNORECASE)
        images_without_alt = sum(1 for img in images if not re.search(r'alt=["\'][^"\']+["\']', img, re.IGNORECASE))
        data["images_without_alt"] = images_without_alt
        if images_without_alt > 3:
            result["seo_issues"].append(f"{images_without_alt} images missing alt")

        # Check robots.txt and sitemap
        try:
            robots_resp = requests.head(f"{base_url}/robots.txt", timeout=3, headers=headers)
            data["has_robots_txt"] = robots_resp.status_code == 200
        except Exception:
            pass
        try:
            sitemap_resp = requests.head(f"{base_url}/sitemap.xml", timeout=3, headers=headers)
            data["has_sitemap"] = sitemap_resp.status_code == 200
        except Exception:
            pass

        # Calculate score
        score = 0
        if data["title"]:
            score += 15
        if data["description"]:
            score += 15
        if data["h1_count"] == 1:
            score += 10
        if data["has_https"]:
            score += 15
        if data["has_viewport"]:
            score += 10
        if data["has_og_tags"]:
            score += 5
        if data["has_canonical"]:
            score += 5
        if data["has_structured_data"]:
            score += 10
        if data["has_robots_txt"]:
            score += 5
        if data["has_sitemap"]:
            score += 5
        if data["has_compression"]:
            score += 5

        result["seo_score"] = min(100, score)
        result["seo_passed"] = result["seo_score"] >= 50 and data["title"] and data["has_https"]

    except requests.exceptions.Timeout:
        result["seo_issues"].append("Timeout")
    except requests.exceptions.ConnectionError:
        result["seo_issues"].append("Connection Failed")
    except Exception as e:
        result["seo_issues"].append(f"Error: {str(e)[:50]}")

    return result


# --- n8n Code Node Entry Point ---
output = []

for item in _input.all():
    data = item.json
    url = data.get("url_checked") or data.get("url") or data.get("website") or data.get("domain")

    check_result = check_seo(url)
    output.append({**data, **check_result})

return output
