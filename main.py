#!/usr/bin/env python3
# main.py
"""
AutoShorts - Automated news shorts video content pipeline

Main entry point that orchestrates:
1. Fetching trending news from signal.bz API
2. Extracting article content and snippets
3. Grouping news into 3-3-4 structure
4. Saving outputs for downstream processing
"""

from config import (
    TOP_NEWS_COUNT,
    REALTIME_KEYWORDS_FILE,
    NEWS_TOP10_FILE,
    NEWS_GROUP_FILE_PATTERN,
)
from scraper import fetch_signal_api
from processor import build_news_top10, group_news_3_3_4, print_groups_for_prompt
from utils import ensure_output_dir, save_json, extract_keywords


def main():
    """Main execution pipeline"""
    # Initialize output directory
    ensure_output_dir()

    # Step 1: Fetch API data
    api_data = fetch_signal_api()
    if not api_data:
        print("\n--- 1단계 실패: API 데이터를 가져오지 못했습니다. ---")
        return 1

    # Step 2: Process trending keywords
    print("\n--- 실시간 검색어 TOP 10 처리 ---")
    realtime = api_data.get("top10", [])
    keywords_list = extract_keywords(realtime, TOP_NEWS_COUNT)

    if len(keywords_list) == TOP_NEWS_COUNT:
        print("\n===== 실시간 검색어 TOP 10 =====")
        for i, kw in enumerate(reversed(keywords_list), start=1):
            print(f"{11 - i}위: {kw}")
        save_json(keywords_list, REALTIME_KEYWORDS_FILE)
    else:
        print(f"[경고] 실검 키워드가 {TOP_NEWS_COUNT}개 미만입니다.")

    # Step 3: Process news articles
    articles = api_data.get("articles", [])
    if not articles:
        print("[경고] 'articles' 데이터가 없어 뉴스 처리를 건너뜁니다.")
        return 0

    print(f"\n--- 인기 뉴스 총 {len(articles)}개 중 상위 {TOP_NEWS_COUNT}개 사용 ---")
    news_top10 = build_news_top10(articles)

    # Save top 10 news
    save_json(news_top10, NEWS_TOP10_FILE)

    # Step 4: Create 3-3-4 groups
    groups = group_news_3_3_4(news_top10)
    print(f"--- 3-3-4 뉴스 그룹 수: {len(groups)} ---")

    # Save each group
    for group_idx, group in enumerate(groups, start=1):
        filepath = NEWS_GROUP_FILE_PATTERN.format(group_idx)
        save_json(group, filepath)

    # Step 5: Print formatted output for prompts
    print_groups_for_prompt(groups)

    print("\n--- 🚀 모든 작업 완료 (실검 + 뉴스 3-3-4 그룹 정리) ---")
    return 0


if __name__ == "__main__":
    exit(main())
