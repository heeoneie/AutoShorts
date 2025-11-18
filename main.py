from bs4 import BeautifulSoup
import re
import requests
import json
import google.generativeai as genai
import os
import time
from urllib.parse import urlparse

# --- 1. Gemini API 키 설정 (직접 입력 방식) ---
API_KEY = "AIzaSyDMzNnRdOY5GLZQpo4Sha1r4en1mtCFfHU"  # 🔑 여기에 실제 키 입력

try:
    if API_KEY == "YOUR_API_KEY_HERE" or not API_KEY:
        raise ValueError("API 키가 설정되지 않았습니다. 코드 상단의 API_KEY를 실제 키로 바꿔주세요.")

    genai.configure(api_key=API_KEY)
    print("--- 0단계: Gemini API 키 로드 성공 ---")

except ValueError as e:
    print(f"\n[에러] {e}\n")
    exit()
except Exception as e:
    print(f"API 키 설정 중 알 수 없는 오류 발생: {e}")
    exit()


# --- 2. 1단계: 데이터 수집 (signal.bz) ---
def scrape_signal_api():
    """ signal.bz 실시간 뉴스 API에서 top10과 articles 수집 """
    api_url = "https://api.signal.bz/news/realtime"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'https://www.signal.bz/'
    }
    try:
        print("--- 1단계 시작: API에서 'top10'과 'articles' 가져오기... ---")
        response = requests.get(api_url, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        print("--- API 데이터 수신 성공! ---")
        return data
    except Exception as e:
        print(f"1단계 API 요청 실패: {e}")
        return None


def _clean_text(t: str) -> str:
    if not t:
        return ""
    t = re.sub(r"\s+", " ", t).strip()
    return t

def _merge_and_trim(base: str, extra: str, max_len: int = 380) -> str:
    """
    base(desc)와 extra(메타/본문)를 자연스럽게 합쳐 길이를 제한.
    """
    base = _clean_text(base)
    extra = _clean_text(extra)
    if not extra:
        return base
    if base and not base.endswith(("…", ".", "!", "?")):
        base = base + "."
    merged = (base + " " + extra).strip()
    if len(merged) > max_len:
        merged = merged[:max_len-1].rstrip() + "…"
    return merged

def enrich_snippet_by_link(link: str, fallback_desc: str) -> str:
    """
    기사 링크의 HTML을 직접 열어 meta 태그/본문을 긁어와 desc를 보강.

    - news.nate.com:
        * div#realArtcContents / div#realArtContents 안의 텍스트를
          extract_nate_body()로 추출해서 사용
    - 그 외:
        * og:description
        * meta[name="description"]
        * 첫 번째 <p>
      순으로 사용
    """
    fallback_desc = fallback_desc or ""
    if not link:
        return _clean_text(fallback_desc)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.google.com/",
    }

    try:
        resp = requests.get(link, headers=headers, timeout=5)
        resp.raise_for_status()
    except Exception:
        # 접속 실패 시 그대로 반환
        return _clean_text(fallback_desc)

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        domain = urlparse(link).netloc

        # 🔹 nate 뉴스: 기사 본문 전체 활용
        if "news.nate.com" in domain:
            container = soup.find(id="realArtcContents") or soup.find(id="realArtContents")
            if container:
                body_text = extract_nate_body(container)
                if body_text:
                    # nate는 기사 전문이니 길이 여유 조금 더 줌
                    return _merge_and_trim(fallback_desc, body_text, max_len=700)

        # 🔹 그 외 사이트: 메타 태그 기반 요약
        # 1) og:description 최우선
        og = soup.find("meta", attrs={"property": "og:description"})
        if og and og.get("content"):
            return _merge_and_trim(fallback_desc, og["content"])

        # 2) meta name="description"
        md = soup.find("meta", attrs={"name": "description"})
        if md and md.get("content"):
            return _merge_and_trim(fallback_desc, md["content"])

        # 3) 본문 첫 단락(사이트마다 다르니 범용적으로 p 하나)
        first_p = soup.find("p")
        if first_p and first_p.get_text(strip=True):
            return _merge_and_trim(fallback_desc, first_p.get_text(strip=True))

        # 4) 아무것도 못 찾으면 fallback만 정리해서 반환
        return _clean_text(fallback_desc)

    except Exception:
        return _clean_text(fallback_desc)

# --- 3. 2단계: Gemini 대본 생성 함수 (1라인: 실검 10-in-1) ---
def generate_line1_script(keywords_list, model):
    """
    실시간 키워드 10개 리스트를 받아 '10-in-1' 쇼츠 대본 1개(JSON)를 생성
    """
    print("\n--- 2단계 (1라인) 시작: Gemini API 호출 (실검 10-in-1)... ---")

    prompt = f"""
    너는 지금부터 '실시간 트렌드 요약' 전문 쇼츠 대본가다.
    입력으로 [키워드 10개 리스트]가 들어온다.
    이 키워드들은 그 자체로 이미 하나의 사건을 요약하고 있다.

    [입력 키워드 리스트]
    {keywords_list}

    [지시 사항]
    1. 이 키워드 리스트를 바탕으로, 10위부터 1위까지 역순으로 소개하는 50초 분량의 '유튜브 쇼츠 나레이션 대본'을 작성하라.
    2. 1위 키워드가 가장 충격적이고 중요한 것처럼 묘사하라.
    3. 아래 [JSON 출력 형식]을 *반드시* 준수하라.
    4. 어떠한 인사말이나 부연 설명도 하지 마라.

    [JSON 출력 형식]
    {{
      "title": "(키워드 기반으로 생성된 자극적인 쇼츠 제목)",
      "hashtags": ["#실시간검색어", "#오늘의이슈", "#트렌드", "(1위 키워드를 반영한 태그)"],
      "script": [
        {{"type": "opening", "text": "방금 뜬 실시간 검색어 TOP 10! 10위부터 갑니다!"}},
        {{"type": "content", "rank": 10, "keyword": "{keywords_list[9]}", "text": "(10위 키워드에 대한 1줄 멘트)"}},
        {{"type": "content", "rank": 9, "keyword": "{keywords_list[8]}", "text": "(9위 키워드에 대한 1줄 멘트)"}},
        {{"type": "content", "rank": 8, "keyword": "{keywords_list[7]}", "text": "(8위 키워드에 대한 1줄 멘트)"}},
        {{"type": "content", "rank": 7, "keyword": "{keywords_list[6]}", "text": "(7위 키워드에 대한 1줄 멘트)"}},
        {{"type": "content", "rank": 6, "keyword": "{keywords_list[5]}", "text": "(6위 키워드에 대한 1줄 멘트)"}},
        {{"type": "content", "rank": 5, "keyword": "{keywords_list[4]}", "text": "(5위 키워드에 대한 1줄 멘트)"}},
        {{"type": "content", "rank": 4, "keyword": "{keywords_list[3]}", "text": "(4위 키워드에 대한 1줄 멘트)"}},
        {{"type": "content", "rank": 3, "keyword": "{keywords_list[2]}", "text": "(3위 키워드에 대한 1줄 멘트)"}},
        {{"type": "content", "rank": 2, "keyword": "{keywords_list[1]}", "text": "(2위 키워드에 대한 1줄 멘트)"}},
        {{"type": "content", "rank": 1, "keyword": "{keywords_list[0]}", "text": "(1위 키워드에 대한 1줄 멘트. 가장 강조)"}},
        {{"type": "closing", "text": "1위 이슈, 어떻게 생각하세요? 댓글로 남겨주세요!"}}
      ]
    }}
    """

    response = None
    try:
        response = model.generate_content(prompt)
        print("--- 2단계 (1라인) 대본 생성 성공! ---")
        return json.loads(response.text)
    except Exception as e:
        print(f"2단계 (1라인) Gemini API 호출 실패: {e}")
        if response and hasattr(response, 'prompt_feedback'):
            print(f"Safety Feedback: {response.prompt_feedback}")
        return None


# --- 4. 2단계: Gemini 대본 생성 함수 (2라인: 뉴스 1-in-1) ---
def generate_line2_script(news_input_dict, model):
    """
    개별 뉴스 1개(dict: title, snippet)를 받아 '1-in-1' 쇼츠 대본 1개(JSON)를 생성
    """
    print(f"\n--- 2단계 (2라인) 시작: Gemini API 호출 (뉴스: {news_input_dict['title'][:20]}... ) ---")

    prompt = f"""
    너는 지금부터 '뉴스 요약 쇼츠' 전문 대본가다.
    입력으로 [뉴스 제목]과 [뉴스 요약]이 들어온다.
    (검색 금지) 오직 이 [제목]과 [뉴스 요약]에 있는 정보*만을* 사용하여, 
    60초 이내의 자극적이고 몰입감 있는 '유튜브 쇼츠 나레이션 대본'을 작성하라.

    [뉴스 제목]
    {news_input_dict['title']}

    [뉴스 요약 (Snippet)]
    {news_input_dict['snippet']}

    [지시 사항]
    1. '결론 선제시' 템플릿을 따라, 훅(Hook)에서 가장 충격적인 결론부터 던져라.
    2. [뉴스 요약]을 바탕으로 사건을 리듬감 있게 전개하라.
    3. 아래 [JSON 출력 형식]을 *반드시* 준수하라.
    4. 어떠한 인사말이나 부연 설명도 하지 마라.

    [JSON 출력 형식]
    {{
      "title": "(입력된 제목과 요약을 바탕으로 생성한 자극적인 쇼츠 제목)",
      "hashtags": ["#오늘의뉴스", "#이슈", "(뉴스 관련 키워드 3개)"],
      "script": [
        {{"type": "hook", "text": "(생성된 훅 멘트. 예: '제주도 수학여행이 비극이 됐습니다.')"}},
        {{"type": "body", "text": "(생성된 본문 멘트 1)"}},
        {{"type": "body", "text": "(생성된 본문 멘트 2)"}},
        {{"type": "body", "text": "(생성된 본문 멘트 3)"}},
        {{"type": "closing", "text": "(생성된 클로징 멘트. 예: '이 사건, 여러분의 생각은?')"}}
      ]
    }}
    """

    response = None
    try:
        response = model.generate_content(prompt)
        print(f"--- 2단계 (2라인) 대본 생성 성공! (뉴스: {news_input_dict['title'][:20]}... ) ---")
        return json.loads(response.text)
    except Exception as e:
        print(f"2단계 (2라인) Gemini API 호출 실패 (뉴스: {news_input_dict['title'][:20]}...): {e}")
        if response and hasattr(response, 'prompt_feedback'):
            print(f"Safety Feedback: {response.prompt_feedback}")
        return None

def extract_nate_body(container) -> str:
    """
    nate 기사 본문 추출 (태그 구조와 무관하게 텍스트 기준으로 처리)
    - realArtcContents / realArtContents 안의 모든 텍스트를 순회
    - 첫 '사진=...' 캡션은 스킵
    - 기자/홍보/저작권/추천기사 패턴이 나오면 거기서 끝냄
    """
    lines = []
    saw_first_photo_caption = False

    # 하단부 끝내는 패턴들
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

        # 2) 두 번째 '사진'부터는 본문이 아니라 기타 캡션일 가능성이 높아서 끊기
        if "사진" in txt and saw_first_photo_caption:
            break

        # 3) 기자 + 이메일 라인 → 여기서 본문 끝
        if "기자" in txt and "@" in txt:
            # print(f"[STOP at reporter line] {txt}")
            break

        # 4) 하단 홍보/저작권 패턴 → 여기서 본문 끝
        if any(pat in txt for pat in END_PATTERNS):
            # print(f"[STOP at footer pattern] {txt}")
            break

        # 5) 추천 기사 리스트 (▶ 로 시작하는 라인) → 여기서 끝내버림
        if txt.startswith("▶"):
            # print(f"[STOP at recommended article] {txt}")
            break

        # 정상 본문
        lines.append(txt)

    return " ".join(lines)

# --- 5. 메인 ---
if __name__ == "__main__":

    # 출력 디렉토리 준비 (한 번만)
    os.makedirs("output/scripts", exist_ok=True)

    # 1단계: 데이터 수집
    api_data = scrape_signal_api()
    if api_data:
        # 모델 설정
        json_config = {"response_mime_type": "application/json"}
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]

        model = genai.GenerativeModel(
            'gemini-2.0-flash',   # 필요 시 'gemini-2.0-pro', 'gemini-1.5-pro' 등으로 교체 가능
            generation_config=json_config,
            safety_settings=safety_settings
        )

        # --- 2단계 (1라인) 실행: 실시간 검색어 10-in-1 ---
        realtime_data = api_data.get('top10', [])
        if realtime_data:
            keywords_list = [item['keyword'] for item in realtime_data]
            line1_script = generate_line1_script(keywords_list, model)
            if line1_script:
                print("\n[=== 1라인 (실검 10-in-1) 대본 ===]")
                print(json.dumps(line1_script, indent=2, ensure_ascii=False))

                # ✅ 실시간 검색어 대본 저장
                with open("output/scripts/00_realtime_script.json", "w", encoding="utf-8") as f:
                    json.dump(line1_script, f, ensure_ascii=False, indent=2)
                print("✅ 실시간 검색어 대본 저장 완료: output/scripts/00_realtime_script.json")
        else:
            print("[경고] 'top10' 데이터가 없어 1라인을 건너뜁니다.")

        # --- 2단계 (2라인) 실행: 인기 뉴스 1-in-1 (최대 10개) ---
        popular_news_data = api_data.get('articles', [])
        if popular_news_data:
            print("\n\n[=== 2라인 (인기 뉴스 1-in-1) 대본 10개 ===]")
            line2_scripts_all = []

            for item in popular_news_data:
                raw_desc = item.get('desc', '') or ''
                link = item.get('link', '')

                # 🔥 여기서 스니펫 보강
                enriched = enrich_snippet_by_link(link, raw_desc)
                print("\n[DEBUG] 제목:", item.get('title', '')[:40])
                print("[DEBUG] 원본 desc:", raw_desc)
                print("[DEBUG] 보강된 snippet:", enriched[:300])
                news_input = {
                    "title": item.get('title', ''),
                    "snippet": enriched
                }

                line2_script = generate_line2_script(news_input, model)
                if line2_script:
                    line2_scripts_all.append(line2_script)
                    print(json.dumps(line2_script, indent=2, ensure_ascii=False))

                    # ✅ 인기 뉴스 대본 저장 (순번 파일)
                    fname = f"output/scripts/{len(line2_scripts_all):02d}_script.json"
                    with open(fname, "w", encoding="utf-8") as f:
                        json.dump(line2_script, f, ensure_ascii=False, indent=2)
                    print(f"✅ 대본 저장: {fname}")

                # 무료 등급 RPM 고려 (필요 시 조절)
                time.sleep(2)

            print(f"\n--- 총 {len(line2_scripts_all)}개의 2라인 대본 생성 완료 ---")
        else:
            print("[경고] 'articles' 데이터가 없어 2라인을 건너뜁니다.")

        print("\n--- 🚀 'main.py' 모든 작업 완료 ---")

    else:
        print("\n--- 1단계 데이터 수집 실패. 2단계를 실행할 수 없습니다. ---")