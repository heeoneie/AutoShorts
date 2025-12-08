# parser.py
"""HTML parsing utilities for news articles"""

import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from config import NATE_END_PATTERNS


def clean_text(text: str) -> str:
    """
    Clean and normalize text by removing extra whitespace.

    Args:
        text: Raw text to clean

    Returns:
        Cleaned text with normalized whitespace
    """
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def extract_nate_body(container) -> str:
    """
    Extract article body from Nate news articles.

    Handles Nate's specific HTML structure by:
    - Skipping the first photo caption
    - Stopping at bylines (with email)
    - Stopping at footer patterns (copyright, promotional text)
    - Stopping at recommended article sections

    Args:
        container: BeautifulSoup element containing the article body

    Returns:
        Extracted and cleaned article text
    """
    lines = []
    saw_first_photo_caption = False

    for raw in container.stripped_strings:
        txt = re.sub(r"\s+", " ", raw).strip()
        if not txt:
            continue

        # Skip first photo caption
        if "사진" in txt and not saw_first_photo_caption:
            saw_first_photo_caption = True
            continue

        # Second "사진" indicates additional captions/metadata - stop here
        if "사진" in txt and saw_first_photo_caption:
            break

        # Byline with email - article body ends here
        if "기자" in txt and "@" in txt:
            break

        # Footer patterns - stop parsing
        if any(pattern in txt for pattern in NATE_END_PATTERNS):
            break

        # Recommended articles section - stop parsing
        if txt.startswith("▶"):
            break

        lines.append(txt)

    return " ".join(lines)


def extract_article_snippet(soup: BeautifulSoup, url: str) -> str:
    """
    Extract article snippet from parsed HTML.

    Tries multiple strategies in order:
    1. For news.nate.com: Custom body extraction
    2. og:description meta tag
    3. meta name="description" tag
    4. First paragraph text

    Args:
        soup: BeautifulSoup parsed HTML
        url: Article URL (used to determine domain-specific parsing)

    Returns:
        Extracted article snippet or empty string if extraction fails
    """
    domain = urlparse(url).netloc

    # Special handling for Nate news
    if "news.nate.com" in domain:
        container = soup.find(id="realArtcContents") or soup.find(id="realArtContents")
        if container:
            body_text = extract_nate_body(container)
            if body_text:
                return clean_text(body_text)

    # Try og:description meta tag
    og_desc = soup.find("meta", attrs={"property": "og:description"})
    if og_desc and og_desc.get("content"):
        return clean_text(og_desc["content"])

    # Try meta name="description"
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        return clean_text(meta_desc["content"])

    # Fallback to first paragraph
    first_p = soup.find("p")
    if first_p and first_p.get_text(strip=True):
        return clean_text(first_p.get_text(strip=True))

    return ""
