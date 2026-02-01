from bs4 import BeautifulSoup
import re
import requests
import json
import os
from urllib.parse import urlparse
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# Firecrawl 설정
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
FIRECRAWL_API_URL = "https://api.firecrawl.dev/v1/scrape"


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
        print("--- API에서 데이터 가져오는 중... ---")
        response = requests.get(api_url, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        print("--- API 데이터 수신 성공 ---")
        return data
    except Exception as e:
        print(f"[에러] signal.bz API 요청 실패: {e}")
        return None


# =========================
# 2. 텍스트 후처리
# =========================

# 제거할 UI/불필요 패턴
REMOVE_PATTERNS = [
    r"본문 바로가기",
    r"광고 영역",
    r"랭킹뉴스.*?공감순",
    r"공유하기.*?URL복사",
    r"_AI_\s*챗.*?기다려주세요\.",
    r"네이트온|페이스북|엑스|카카오",
    r"가\s*_\d_\s*(작게|보통|크게|아주 크게|가장 크게)",
    r"전체 내용을 이해하기 위해서는.*?확인하는 것이 더 좋습니다\.",
    r"기사 제목과 본문 내용을 자동 요약한 내용입니다\.",
    r"원문기사전송.*?\d{4}-\d{2}-\d{2}",
    r"최종수정.*?\d{4}-\d{2}-\d{2}",
    r"\d+\s*-\s*\d+",  # 조회수/댓글수 패턴
    r"무단전재 및 재배포 금지",
    r"Copyright\s*ⓒ.*",
    r"< Copyright.*?>",
    r"▶.*",  # 추천기사
    r"조선닷컴 핫 뉴스 Best.*",
    r"\[.*?기자\]",
    r"기자\s*[\w.]+@[\w.]+",  # 기자 이메일
]


def clean_article_text(text: str) -> str:
    """기사 본문에서 불필요한 UI 요소 및 패턴 제거"""
    if not text:
        return ""

    # 패턴 제거
    for pattern in REMOVE_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.DOTALL)

    # 연속 공백 정리
    text = re.sub(r"\s+", " ", text).strip()

    # 너무 짧은 문장 조각 제거 (3글자 이하)
    sentences = text.split(".")
    sentences = [s.strip() for s in sentences if len(s.strip()) > 3]
    text = ". ".join(sentences)

    return text


# =========================
# 3. Firecrawl API로 기사 본문 추출
# =========================

def scrape_with_firecrawl(url: str) -> str:
    """Firecrawl API를 사용해 기사 본문을 추출"""
    if not FIRECRAWL_API_KEY:
        return ""

    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "url": url,
        "formats": ["markdown"],
        "onlyMainContent": True,
        "timeout": 30000
    }

    try:
        resp = requests.post(
            FIRECRAWL_API_URL,
            headers=headers,
            json=payload,
            timeout=35
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("success"):
            markdown = data.get("data", {}).get("markdown", "")
            # 마크다운에서 텍스트만 추출
            text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', markdown)
            text = re.sub(r'!\[.*?\]\([^)]+\)', '', text)
            text = re.sub(r'#+\s*', '', text)
            text = re.sub(r'\*+', '', text)
            text = re.sub(r'\n+', ' ', text)
            # 후처리 적용
            return clean_article_text(text)

        return ""
    except Exception as e:
        print(f"    [Firecrawl 실패] {e}")
        return ""


def build_snippet_from_link_legacy(link: str) -> str:
    """기존 BeautifulSoup 기반 추출 (폴백용)"""
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
        print(f"    [Legacy 실패] {e}")
        return ""

    try:
        soup = BeautifulSoup(resp.text, "html.parser")

        og = soup.find("meta", attrs={"property": "og:description"})
        if og and og.get("content"):
            return clean_article_text(og["content"])

        md = soup.find("meta", attrs={"name": "description"})
        if md and md.get("content"):
            return clean_article_text(md["content"])

        return ""
    except Exception as e:
        print(f"    [Legacy 파싱 실패] {e}")
        return ""


def fetch_article_content(url: str) -> str:
    """기사 본문 추출 (Firecrawl 우선, 폴백 지원)"""
    if not url:
        return ""

    if FIRECRAWL_API_KEY:
        content = scrape_with_firecrawl(url)
        if content and len(content) > 100:
            return content

    return build_snippet_from_link_legacy(url)


def fetch_article_image(url: str) -> str:
    """기사 og:image URL 추출"""
    if not url:
        return ""

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    try:
        resp = requests.get(url, headers=headers, timeout=7)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # og:image 찾기
        og_image = soup.find("meta", attrs={"property": "og:image"})
        if og_image and og_image.get("content"):
            return og_image["content"]

        # twitter:image 폴백
        tw_image = soup.find("meta", attrs={"name": "twitter:image"})
        if tw_image and tw_image.get("content"):
            return tw_image["content"]

        return ""
    except Exception as e:
        print(f"    [이미지 URL 추출 실패] {e}")
        return ""


def fetch_keyword_image(summary_url: str) -> str:
    """키워드 요약 페이지에서 관련 뉴스 이미지 추출"""
    if not summary_url or not FIRECRAWL_API_KEY:
        return ""

    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "url": summary_url,
        "formats": ["html"],
        "waitFor": 3000,
        "timeout": 30000
    }

    try:
        resp = requests.post(
            FIRECRAWL_API_URL,
            headers=headers,
            json=payload,
            timeout=35
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            return ""

        html = data.get("data", {}).get("html", "")

        # 네이버 뉴스 링크 추출
        import re
        naver_links = re.findall(r'https://n\.news\.naver\.com/[^"\'>\s]+', html)

        if naver_links:
            # 첫 번째 뉴스에서 og:image 추출
            return fetch_article_image(naver_links[0])

        return ""
    except Exception as e:
        print(f"    [키워드 이미지 추출 실패] {e}")
        return ""


# =========================
# 4. 메인 실행부
# =========================

if __name__ == "__main__":
    # 출력 디렉토리 준비
    os.makedirs("output/news", exist_ok=True)

    # API 데이터 수집
    api_data = scrape_signal_api()
    if not api_data:
        print("\n[에러] API 데이터를 가져오지 못했습니다.")
        exit(1)

    # -------------------
    # (A) 실시간 검색어 TOP 10 - 단일 파일 저장
    # -------------------
    print("\n" + "=" * 50)
    print("실시간 검색어 TOP 10 수집")
    print("=" * 50)

    realtime = api_data.get("top10", [])
    keywords = []

    for i, item in enumerate(realtime[:10], start=1):
        keyword = item.get("keyword", "")
        summary_url = item.get("summary", "")

        print(f"\n  [{i}/10] {keyword}")

        # 관련 뉴스 이미지 추출
        image_url = ""
        if summary_url:
            image_url = fetch_keyword_image(summary_url)
            if image_url:
                print(f"    -> 이미지 URL 확인")
            else:
                print(f"    -> 이미지 없음")

        keywords.append({
            "rank": i,
            "keyword": keyword,
            "image_url": image_url
        })

    # 단일 파일로 저장
    with open("output/keywords.json", "w", encoding="utf-8") as f:
        json.dump(keywords, f, ensure_ascii=False, indent=2)

    print(f"\n저장됨: output/keywords.json")

    # -------------------
    # (B) 인기 뉴스 TOP 10 - 개별 저장 (본문 포함)
    # -------------------
    print("\n" + "=" * 50)
    print("인기 뉴스 TOP 10 수집")
    print("=" * 50)

    articles = api_data.get("articles", [])
    news_list = []

    for i, item in enumerate(articles[:10], start=1):
        title = (item.get("title") or "").strip()
        url = (item.get("link") or "").strip()

        print(f"\n[{i}/10] {title[:40]}...")

        # 본문 수집
        content = fetch_article_content(url)

        # 이미지 URL 수집
        image_url = fetch_article_image(url)

        if content:
            print(f"    -> 본문 성공 ({len(content)}자)")
        else:
            print(f"    -> 본문 수집 실패")

        if image_url:
            print(f"    -> 이미지 URL 확인")
        else:
            print(f"    -> 이미지 없음")

        news_data = {
            "rank": i,
            "title": title,
            "url": url,
            "content": content,
            "image_url": image_url
        }
        news_list.append(news_data)

        # 개별 파일 저장
        path = f"output/news/news_{i:02d}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(news_data, f, ensure_ascii=False, indent=2)

    print(f"\n저장됨: output/news/news_01~10.json")

    # -------------------
    # 완료 메시지
    # -------------------
    success_count = len([n for n in news_list if n["content"]])

    print("\n" + "=" * 50)
    print("수집 완료!")
    print("=" * 50)
    print(f"검색어: {len(keywords)}개")
    print(f"뉴스: {success_count}/{len(news_list)}개 본문 수집 성공")
    print(f"\n저장 위치:")
    print(f"  - output/keywords.json")
    print(f"  - output/news/news_01~10.json")
