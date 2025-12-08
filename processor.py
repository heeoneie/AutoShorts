# processor.py
"""News processing and grouping utilities"""

from typing import List, Dict, Any
from scraper import fetch_article_content
from config import TOP_NEWS_COUNT


def build_news_top10(api_articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Process top 10 news articles from API data.

    Fetches full article content for each news item and builds
    structured data with rank, title, URL, and snippet.

    Args:
        api_articles: List of article dictionaries from API

    Returns:
        List of processed news items with rank, title, url, and snippet fields
    """
    news_items = []

    for idx, item in enumerate(api_articles[:TOP_NEWS_COUNT], start=1):
        title = (item.get("title") or "").strip()
        url = (item.get("link") or "").strip()

        print(f"\n[INFO] ({idx}) 기사 처리 중: {title[:50]}")

        snippet = fetch_article_content(url)
        if not snippet:
            print("  -> [주의] 본문/요약을 가져오지 못했습니다.")
        else:
            print(f"  -> [OK] snippet 길이: {len(snippet)}")

        news_items.append(
            {
                "rank": idx,
                "title": title,
                "url": url,
                "snippet": snippet,
            }
        )

    return news_items


def group_news_3_3_4(news_items: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """
    Split top 10 news into 3-3-4 grouping pattern.

    Groups:
    - Group 1: Items 1-3
    - Group 2: Items 4-6
    - Group 3: Items 7-10

    Args:
        news_items: List of news items (should be 10 items)

    Returns:
        List of groups, each containing a subset of news items
    """
    groups = []

    if len(news_items) >= 3:
        groups.append(news_items[0:3])  # Items 1-3
    if len(news_items) >= 6:
        groups.append(news_items[3:6])  # Items 4-6
    if len(news_items) > 6:
        groups.append(news_items[6:10])  # Items 7-10 (up to 4 items)

    return groups


def print_groups_for_prompt(groups: List[List[Dict[str, Any]]]) -> None:
    """
    Print news groups in a format suitable for ChatGPT prompts.

    Outputs each group with formatted title and summary sections.

    Args:
        groups: List of news groups to print
    """
    for group_idx, group in enumerate(groups, start=1):
        print("\n" + "=" * 60)
        print(f"=== 뉴스 그룹 {group_idx} (총 {len(group)}개) ===")
        print("=" * 60)

        for item in group:
            rank = item["rank"]
            title = item["title"]
            snippet = item["snippet"]

            print(f"\n[뉴스 {rank} 제목]\n{title}")
            print(f"\n[뉴스 {rank} 요약]\n{snippet}\n")
