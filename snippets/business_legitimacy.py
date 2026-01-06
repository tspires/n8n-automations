# snippet: business_legitimacy
"""
n8n Python Code Node: Business Legitimacy Check
Detects parked domains, placeholder pages, and other low-quality sites.

Input: Expects items with 'url' field (or url_checked from previous step)
Output: Adds 'is_real_business', 'legitimacy_score', 'red_flags'
"""

import re
import requests

# Parked domain indicators
PARKED_PATTERNS = [
    r'buy\s+this\s+domain',
    r'domain\s+(is\s+)?for\s+sale',
    r'parked\s+(by|domain|free)',
    r'godaddy\.com/domain',
    r'sedo\.com',
    r'afternic\.com',
    r'hugedomains\.com',
    r'dan\.com',
    r'namecheap\.com.*parking',
    r'this\s+domain\s+(may\s+be|is)\s+for\s+sale',
]

# Under construction indicators
CONSTRUCTION_PATTERNS = [
    r'under\s+construction',
    r'coming\s+soon',
    r'launching\s+soon',
    r'website\s+(is\s+)?(under|being)\s+(construction|built|developed)',
    r'check\s+back\s+(soon|later)',
    r'we\'?re\s+working\s+on\s+(it|something)',
    r'site\s+under\s+development',
    r'opening\s+soon',
]

# Generic template indicators (often indicates abandoned/placeholder)
TEMPLATE_PATTERNS = [
    r'lorem\s+ipsum',
    r'your\s+company\s+(name|slogan)',
    r'sample\s+text\s+here',
    r'insert\s+.*\s+here',
    r'example\.com',
    r'email@example',
    r'\[your\s+',
    r'welcome\s+to\s+wordpress',
    r'just\s+another\s+wordpress\s+site',
]

REQUEST_TIMEOUT = 10
MIN_CONTENT_LENGTH = 500  # Characters - very thin content is suspect
MIN_WORD_COUNT = 50  # Minimum words for legitimate business


def check_legitimacy(url: str) -> dict:
    """
    Analyze a URL for business legitimacy signals.
    """
    result = {
        "is_real_business": False,
        "legitimacy_score": 0,
        "red_flags": [],
        "content_length": 0,
        "word_count": 0,
    }

    if not url:
        result["red_flags"].append("No URL provided")
        return result

    # Normalize URL
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"

    headers = {"User-Agent": "Mozilla/5.0 (compatible; ProspectValidator/1.0)"}

    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True, headers=headers)

        # Check for redirect to completely different domain (potential hijack/parked)
        final_domain = response.url.split('/')[2].lower()
        original_domain = url.split('/')[2].lower()
        if final_domain != original_domain:
            # Allow www prefix differences
            if not (final_domain.replace('www.', '') == original_domain.replace('www.', '')):
                result["red_flags"].append(f"Redirects to different domain: {final_domain}")

        if response.status_code >= 400:
            result["red_flags"].append(f"HTTP error: {response.status_code}")
            return result

        content = response.text.lower()
        content_length = len(content)
        result["content_length"] = content_length

        # Extract visible text (strip HTML tags for word count)
        visible_text = re.sub(r'<[^>]+>', ' ', content)
        visible_text = re.sub(r'\s+', ' ', visible_text).strip()
        words = visible_text.split()
        word_count = len(words)
        result["word_count"] = word_count

        # Check for parked domain patterns
        for pattern in PARKED_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                result["red_flags"].append("Parked domain detected")
                break

        # Check for under construction
        for pattern in CONSTRUCTION_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                result["red_flags"].append("Under construction page")
                break

        # Check for template/placeholder content
        for pattern in TEMPLATE_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                result["red_flags"].append("Placeholder/template content")
                break

        # Check content length
        if content_length < MIN_CONTENT_LENGTH:
            result["red_flags"].append("Very thin content")

        if word_count < MIN_WORD_COUNT:
            result["red_flags"].append("Low word count")

        # Calculate legitimacy score (0-100)
        score = 100

        # Deduct points for each red flag
        score -= len(result["red_flags"]) * 25

        # Bonus for substantial content
        if word_count > 200:
            score += 10
        if word_count > 500:
            score += 10

        result["legitimacy_score"] = max(0, min(100, score))
        result["is_real_business"] = len(result["red_flags"]) == 0 and word_count >= MIN_WORD_COUNT

    except requests.exceptions.Timeout:
        result["red_flags"].append("Request timeout")
    except requests.exceptions.SSLError:
        result["red_flags"].append("SSL error")
    except requests.exceptions.ConnectionError:
        result["red_flags"].append("Connection failed")
    except Exception as e:
        result["red_flags"].append(f"Error: {str(e)[:50]}")

    return result


# --- n8n Code Node Entry Point ---
output = []

for item in _input.all():
    data = item.json

    # Use url_checked from previous step, or fall back to url field
    url = data.get("url_checked") or data.get("url") or data.get("website") or data.get("domain")

    check_result = check_legitimacy(url)
    output.append({**data, **check_result})

return output
