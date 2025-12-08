# scraper.py
"""Web scraping functionality for news data"""

import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any

from config import (
    SIGNAL_API_URL,
    API_HEADERS,
    DEFAULT_HEADERS,
    API_TIMEOUT,
    ARTICLE_TIMEOUT,
)
from parser import extract_article_snippet


def fetch_signal_api() -> Optional[Dict[str, Any]]:
    """
    Fetch real-time news data from signal.bz API.

    Returns:
        Dictionary containing 'top10' (trending keywords) and 'articles' (news items)
        Returns None if request fails
    """
    try:
        print("--- 1단계: API에서 'top10'과 'articles' 가져오기... ---")
        response = requests.get(SIGNAL_API_URL, headers=API_HEADERS, timeout=API_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        print("--- API 데이터 수신 성공 ---")
        return data
    except Exception as e:
        print(f"[에러] signal.bz API 요청 실패: {e}")
        return None


def fetch_article_content(url: str) -> str:
    """
    Fetch and extract content snippet from a news article URL.

    Args:
        url: Article URL to fetch

    Returns:
        Extracted article snippet/summary text
        Returns empty string if fetch or parsing fails
    """
    if not url:
        return ""

    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=ARTICLE_TIMEOUT)
        response.raise_for_status()
    except Exception as e:
        print(f"[경고] 기사 요청 실패 ({url}): {e}")
        return ""

    try:
        soup = BeautifulSoup(response.text, "html.parser")
        return extract_article_snippet(soup, url)
    except Exception as e:
        print(f"[경고] HTML 파싱 실패 ({url}): {e}")
        return ""
