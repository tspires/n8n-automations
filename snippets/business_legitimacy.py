# snippet: business_legitimacy
"""
n8n Python Code Node: Business Legitimacy Check
Detects parked domains, placeholder pages, and other low-quality sites.

Input: Expects items with 'url' field (or url_checked from previous step)
Output: legitimacy_passed, legitimacy_score, legitimacy_issues, legitimacy_data
"""

import re
import requests

REQUEST_TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (compatible; ProspectValidator/1.0)"

# Detection patterns
PARKED_PATTERNS = [
    r'buy\s+this\s+domain', r'domain\s+(is\s+)?for\s+sale', r'parked\s+(by|domain|free)',
    r'godaddy\.com/domain', r'sedo\.com', r'afternic\.com', r'hugedomains\.com', r'dan\.com',
    r'this\s+domain\s+(may\s+be|is)\s+for\s+sale',
]

CONSTRUCTION_PATTERNS = [
    r'under\s+construction', r'coming\s+soon', r'launching\s+soon',
    r'check\s+back\s+(soon|later)', r'site\s+under\s+development', r'opening\s+soon',
]

TEMPLATE_PATTERNS = [
    r'lorem\s+ipsum', r'your\s+company\s+(name|slogan)', r'sample\s+text\s+here',
    r'\[your\s+', r'just\s+another\s+wordpress\s+site',
]

MIN_WORD_COUNT = 50


def check_legitimacy(url: str) -> dict:
    """Analyze a URL for business legitimacy signals."""
    result = {
        "legitimacy_passed": False,
        "legitimacy_score": 0,
        "legitimacy_issues": [],
        "legitimacy_data": {
            "word_count": 0,
            "content_length": 0,
            "redirected_to": None,
        },
    }

    if not url:
        result["legitimacy_issues"].append("No URL provided")
        return result

    # Normalize URL
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"

    headers = {"User-Agent": USER_AGENT}

    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True, headers=headers)

        # Check for redirect to different domain
        final_domain = response.url.split('/')[2].lower().replace('www.', '')
        original_domain = url.split('/')[2].lower().replace('www.', '')
        if final_domain != original_domain:
            result["legitimacy_data"]["redirected_to"] = final_domain
            result["legitimacy_issues"].append(f"Redirects to {final_domain}")

        if response.status_code >= 400:
            result["legitimacy_issues"].append(f"HTTP {response.status_code}")
            return result

        content = response.text
        content_lower = content.lower()
        result["legitimacy_data"]["content_length"] = len(content)

        # Extract visible text
        visible_text = re.sub(r'<script[^>]*>.*?</script>', ' ', content, flags=re.DOTALL | re.IGNORECASE)
        visible_text = re.sub(r'<style[^>]*>.*?</style>', ' ', visible_text, flags=re.DOTALL | re.IGNORECASE)
        visible_text = re.sub(r'<[^>]+>', ' ', visible_text)
        visible_text = re.sub(r'\s+', ' ', visible_text).strip()
        word_count = len(visible_text.split())
        result["legitimacy_data"]["word_count"] = word_count

        # Check patterns
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

        # Calculate score
        score = 100
        score -= len(result["legitimacy_issues"]) * 25
        if word_count > 200:
            score += 10
        if word_count > 500:
            score += 10

        result["legitimacy_score"] = max(0, min(100, score))
        result["legitimacy_passed"] = len(result["legitimacy_issues"]) == 0 and word_count >= MIN_WORD_COUNT

    except requests.exceptions.Timeout:
        result["legitimacy_issues"].append("Timeout")
    except requests.exceptions.SSLError:
        result["legitimacy_issues"].append("SSL Error")
    except requests.exceptions.ConnectionError:
        result["legitimacy_issues"].append("Connection Failed")
    except Exception as e:
        result["legitimacy_issues"].append(f"Error: {str(e)[:50]}")

    return result


# --- n8n Code Node Entry Point ---
output = []

for item in _input.all():
    data = item.json
    url = data.get("url_checked") or data.get("url") or data.get("website") or data.get("domain")

    check_result = check_legitimacy(url)
    output.append({**data, **check_result})

return output
