from bs4 import BeautifulSoup
import re
import requests
import json
import os
from urllib.parse import urlparse

# =========================
# 1. signal.bz API 호출
# =========================

def scrape_signal_api():
    """signal.bz 실시간 뉴스 API에서 top10과 articles 수집"""
    api_url = "https://api.signal.bz/news/realtime"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        ),
        "Referer": "https://www.signal.bz/",
    }
    try:
        print("--- 1단계: API에서 'top10'과 'articles' 가져오기... ---")
        response = requests.get(api_url, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        print("--- API 데이터 수신 성공 ---")
        return data
    except Exception as e:
        print(f"[에러] signal.bz API 요청 실패: {e}")
        return None


# =========================
# 2. 텍스트 유틸
# =========================

def _clean_text(t: str) -> str:
    if not t:
        return ""
    t = re.sub(r"\s+", " ", t).strip()
    return t


# =========================
# 3. NATE 전용 본문 추출
# =========================

def extract_nate_body(container) -> str:
    """
    nate 기사 본문 추출 (태그 구조와 무관하게 텍스트 기준으로 처리)
    - realArtcContents / realArtContents 안의 모든 텍스트를 순회
    - 첫 '사진=...' 캡션은 스킵
    - 기자/홍보/저작권/추천기사 패턴이 나오면 거기서 끝냄
    """
    lines = []
    saw_first_photo_caption = False

    END_PATTERNS = [
        "MBN 화제뉴스",
        "네이버에서 'MBN뉴스'",
        "Make a Better Next, MBN",
        "MBN 무료 고화질 온에어 서비스 GO!",
        "MBN(www.mbn.co.kr)",
        "무단전재 및 재배포 금지",
        "< Copyright",
        "Copyright ⓒ",
    ]

    for raw in container.stripped_strings:
        txt = re.sub(r"\s+", " ", raw).strip()
        if not txt:
            continue

        # 1) 첫 사진 캡션은 스킵
        if "사진" in txt and not saw_first_photo_caption:
            saw_first_photo_caption = True
            continue

        # 2) 두 번째 '사진' 나오면 이후는 캡션/기타일 확률 높아서 종료
        if "사진" in txt and saw_first_photo_caption:
            break

        # 3) 기자 + 이메일 라인 → 여기서 본문 끝
        if "기자" in txt and "@" in txt:
            break

        # 4) 하단 홍보/저작권 패턴 → 종료
        if any(pat in txt for pat in END_PATTERNS):
            break

        # 5) 추천 기사 리스트 (▶ 로 시작) → 종료
        if txt.startswith("▶"):
            break

        lines.append(txt)

    return " ".join(lines)


# =========================
# 4. 기사 링크로 들어가서 요약 재료 뽑기
# =========================

def build_snippet_from_link(link: str) -> str:
    """
    기사 링크의 HTML을 열어서 '요약 재료' 텍스트를 만들어 반환.
    - news.nate.com: 전용 extract_nate_body 사용 (본문 위주)
    - 기타: og:description / meta[name=description] / 첫 번째 <p> 텍스트
    """
    if not link:
        return ""

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.google.com/",
    }

    try:
        resp = requests.get(link, headers=headers, timeout=7)
        resp.raise_for_status()
    except Exception as e:
        print(f"[경고] 기사 요청 실패 ({link}): {e}")
        return ""

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        domain = urlparse(link).netloc

        # 🔹 1) nate 뉴스면 본문을 최대한 활용
        if "news.nate.com" in domain:
            container = soup.find(id="realArtcContents") or soup.find(id="realArtContents")
            if container:
                body_text = extract_nate_body(container)
                if body_text:
                    return _clean_text(body_text)

        # 🔹 2) 그 외: 메타 태그 / 첫 단락 기반
        # 2-1) og:description
        og = soup.find("meta", attrs={"property": "og:description"})
        if og and og.get("content"):
            return _clean_text(og["content"])

        # 2-2) meta name="description"
        md = soup.find("meta", attrs={"name": "description"})
        if md and md.get("content"):
            return _clean_text(md["content"])

        # 2-3) 첫 번째 <p>
        first_p = soup.find("p")
        if first_p and first_p.get_text(strip=True):
            return _clean_text(first_p.get_text(strip=True))

        return ""
    except Exception as e:
        print(f"[경고] HTML 파싱 실패 ({link}): {e}")
        return ""


# =========================
# 5. 뉴스 Top10 + 3-3-4 그룹 만들기
# =========================

def build_news_top10(api_articles):
    """
    signal.bz 'articles' 배열에서 상위 10개를 뽑아
    [{rank, title, url, snippet}] 리스트로 반환
    """
    news_items = []
    for idx, item in enumerate(api_articles[:10], start=1):
        title = (item.get("title") or "").strip()
        url = (item.get("link") or "").strip()
        print(f"\n[INFO] ({idx}) 기사 처리 중: {title[:50]}")

        snippet = build_snippet_from_link(url)
        if not snippet:
            print("  -> [주의] 본문/요약을 가져오지 못했습니다.")
        else:
            print("  -> [OK] snippet 길이:", len(snippet))

        news_items.append(
            {
                "rank": idx,
                "title": title,
                "url": url,
                "snippet": snippet,
            }
        )

    return news_items


def group_news_3_3_4(news_items):
    """
    Top10 뉴스 리스트를 3-3-4로 그룹 나누기
      - 1그룹: 1~3
      - 2그룹: 4~6
      - 3그룹: 7~10
    """
    groups = []

    if len(news_items) >= 3:
        groups.append(news_items[0:3])   # 1~3
    if len(news_items) >= 6:
        groups.append(news_items[3:6])   # 4~6
    if len(news_items) > 6:
        groups.append(news_items[6:10])  # 7~10 (최대 4개)

    return groups


# =========================
# 6. 콘솔 출력용 포맷 (ChatGPT에 붙여넣기용)
# =========================

def print_groups_for_prompt(groups):
    """
    ChatGPT에 바로 붙여넣기 좋은 형식으로
    [뉴스 n 제목] / [뉴스 n 요약] 형태 출력
    """
    for gi, group in enumerate(groups, start=1):
        print("\n" + "=" * 60)
        print(f"=== 뉴스 그룹 {gi} (총 {len(group)}개) ===")
        print("=" * 60)

        for item in group:
            r = item["rank"]
            title = item["title"]
            snippet = item["snippet"]

            print(f"\n[뉴스 {r} 제목]\n{title}")
            print(f"\n[뉴스 {r} 요약]\n{snippet}\n")


# =========================
# 7. 메인 실행부
# =========================

if __name__ == "__main__":
    # 출력 디렉토리 준비
    os.makedirs("output", exist_ok=True)

    # 1단계: 데이터 수집
    api_data = scrape_signal_api()
    if not api_data:
        print("\n--- 1단계 실패: API 데이터를 가져오지 못했습니다. ---")
        exit(1)

    # -------------------
    # (A) 실검 TOP 10 키워드
    # -------------------
    realtime = api_data.get("top10", [])
    keywords_list = [item["keyword"] for item in realtime][:10]

    if len(keywords_list) == 10:
        print("\n===== 실시간 검색어 TOP 10 =====")
        for i, kw in enumerate(reversed(keywords_list), start=1):
            # 10위부터 1위까지 보고 싶으면 reversed 사용
            print(f"{11 - i}위: {kw}")
        # JSON 파일로도 저장
        with open("output/realtime_top10_keywords.json", "w", encoding="utf-8") as f:
            json.dump(keywords_list, f, ensure_ascii=False, indent=2)
        print("✅ 실시간 검색어 키워드 저장: output/realtime_top10_keywords.json")
    else:
        print("[경고] 실검 키워드가 10개 미만입니다.")

    # -------------------
    # (B) 인기 뉴스 10개 + 3-3-4 그룹
    # -------------------
    articles = api_data.get("articles", [])
    if not articles:
        print("[경고] 'articles' 데이터가 없어 뉴스 처리를 건너뜁니다.")
        exit(0)

    print(f"\n--- 인기 뉴스 총 {len(articles)}개 중 상위 10개 사용 ---")
    news_top10 = build_news_top10(articles)

    # Top10 전체를 JSON으로 저장
    with open("output/news_top10.json", "w", encoding="utf-8") as f:
        json.dump(news_top10, f, ensure_ascii=False, indent=2)
    print("✅ Top10 뉴스 저장: output/news_top10.json")

    # 3-3-4 그룹 나누기
    groups = group_news_3_3_4(news_top10)
    print(f"--- 3-3-4 뉴스 그룹 수: {len(groups)} ---")

    # 각 그룹별 JSON 저장 + 콘솔 출력
    for gi, group in enumerate(groups, start=1):
        path = f"output/news_group_{gi:02d}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(group, f, ensure_ascii=False, indent=2)
        print(f"✅ 뉴스 그룹 {gi} 저장: {path}")

    # 프롬프트에 붙여넣기 좋은 형식으로 콘솔 출력
    print_groups_for_prompt(groups)

    print("\n--- 🚀 모든 작업 완료 (실검 + 뉴스 3-3-4 그룹 정리) ---")
