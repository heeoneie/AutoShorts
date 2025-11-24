from bs4 import BeautifulSoup
import re
import requests
import json
import google.generativeai as genai
import os
import time
from urllib.parse import urlparse

# --- 1. Gemini API 키 설정 (직접 입력 방식) ---
API_KEY = ""  # 🔑 여기에 실제 키 입력

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
        print("--- 1단계 시작: API에서 'top10'과 'articles' 가져오기... ---")
        response = requests.get(api_url, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        print("--- API 데이터 수신 성공! ---")
        return data
    except Exception as e:
        print(f"1단계 API 요청 실패: {e}")
        return None


# --- 3. 텍스트 전처리 & 스니펫 보강 유틸 ---

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
        merged = merged[: max_len - 1].rstrip() + "…"
    return merged


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
            break

        # 4) 하단 홍보/저작권 패턴 → 여기서 본문 끝
        if any(pat in txt for pat in END_PATTERNS):
            break

        # 5) 추천 기사 리스트 (▶ 로 시작하는 라인) → 여기서 끝내버림
        if txt.startswith("▶"):
            break

        # 정상 본문
        lines.append(txt)

    return " ".join(lines)


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


# --- 4. 2단계: Gemini 대본 생성 (1라인: 실검 10-in-1) ---

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
        if response and hasattr(response, "prompt_feedback"):
            print(f"Safety Feedback: {response.prompt_feedback}")
        return None


# --- 5. 2단계: Gemini 대본 생성 (멀티 뉴스: 3-3-4 묶음) ---

def generate_multi_news_script(news_list, model):
    """
    여러 개 뉴스(최대 4개)를 받아서
    '뉴스 여러 건을 한 번에 소개하는 쇼츠 대본' 1개(JSON) 생성.

    news_list 예시:
    [
      {"title": "...", "snippet": "..."},
      {"title": "...", "snippet": "..."},
      ...
    ]
    """
    news_count = len(news_list)
    print(
        f"\n--- 2단계 (멀티 뉴스) 시작: Gemini API 호출 (뉴스 {news_count}개 묶음) ---"
    )

    # 🔹 뉴스 개수에 따라 문장 수 가이드 다르게 주기
    if news_count == 3:
        per_news_guide = (
            "각 뉴스별로 3~4문장 정도로 요약하되, 사건의 흐름과 의미가 드러나게 작성하라."
        )
    elif news_count == 4:
        per_news_guide = (
            "각 뉴스별로 2~3문장 정도로 요약하되, 핵심 사건과 포인트만 뽑아서 작성하라."
        )
    else:
        # 방어적 기본값 (혹시 2개나 5개 이상이 들어오는 경우)
        per_news_guide = (
            "각 뉴스별로 2~3문장 정도로 요약하되, 핵심 사건과 포인트만 뽑아서 작성하라."
        )

    # 프롬프트용으로 뉴스 나열
    news_block = ""
    for idx, news in enumerate(news_list, start=1):
        news_block += f"[뉴스 {idx} 제목]\n{news['title']}\n\n[뉴스 {idx} 요약]\n{news['snippet']}\n\n"

    prompt = f"""
    너는 지금부터 '뉴스 요약 쇼츠' 전문 대본가다.
    아래에 3~4개의 뉴스 제목과 요약이 주어진다.
    이 뉴스를 한 개의 유튜브 쇼츠로 엮어서,
    60초 내외 분량의 나레이션 대본을 작성하라.

    [입력 뉴스 개수] {news_count}개

    [입력 뉴스들]
    {news_block}

    [지시 사항]
    1. 훅(Hook)에서는 가장 자극적이거나 사람들이 관심 가질 만한 포인트를 한 문장으로 던져라.
    2. 그 다음, 뉴스 1번부터 {news_count}번까지 차례대로 소개하되,
       {per_news_guide}
    3. 마지막 클로징에서는, 전체 뉴스를 관통하는 공통점이나 시청자에게 던지는 질문으로 마무리하라.
    4. 오직 위에 주어진 [뉴스 제목]과 [뉴스 요약] 내용만 사용하고, 검색하거나 새로운 팩트를 만들지 마라.
    5. 아래 [JSON 출력 형식]을 *반드시* 지켜라. 한국어로 작성하라.
    6. 인사말, 해시태그 설명 등은 넣지 말고, 바로 내용만 작성하라.

    [JSON 출력 형식]
    {{
      "title": "(여러 뉴스를 아우르는 자극적인 쇼츠 제목)",
      "hashtags": ["#오늘의뉴스", "#이슈모음", "(뉴스 공통 키워드 2~3개)"],
      "script": [
        {{"type": "hook", "text": "(시작 훅 멘트 한 문장)"}},
        {{"type": "story", "index": 1, "text": "(뉴스 1번 요약 멘트)"}},
        {{"type": "story", "index": 2, "text": "(뉴스 2번 요약 멘트)"}},
        {{"type": "story", "index": 3, "text": "(뉴스 3번 요약 멘트)"}},
        {{"type": "story", "index": 4, "text": "(뉴스 4번이 있을 경우에만 작성)"}},
        {{"type": "closing", "text": "(전체 뉴스를 정리하며 시청자에게 질문을 던지는 멘트)"}}
      ]
    }}
    """

    response = None
    try:
        response = model.generate_content(prompt)
        print(
            f"--- 2단계 (멀티 뉴스) 대본 생성 성공! (뉴스 {news_count}개 묶음) ---"
        )
        return json.loads(response.text)
    except Exception as e:
        print(
            f"2단계 (멀티 뉴스) Gemini API 호출 실패 (뉴스 {news_count}개 묶음): {e}"
        )
        if response and hasattr(response, "prompt_feedback"):
            print(f"Safety Feedback: {response.prompt_feedback}")
        return None


# --- 6. 메인 ---
if __name__ == "__main__":

    # 출력 디렉토리 준비 (한 번만)
    os.makedirs("output/scripts", exist_ok=True)

    # 1단계: 데이터 수집
    api_data = scrape_signal_api()
    if not api_data:
        print("\n--- 1단계 데이터 수집 실패. 2단계를 실행할 수 없습니다. ---")
        exit()

    # 모델 설정
    json_config = {"response_mime_type": "application/json"}
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]

    model = genai.GenerativeModel(
        "gemini-2.0-flash",
        generation_config=json_config,
        safety_settings=safety_settings,
    )

    # --- 2단계 (1라인) 실행: 실시간 검색어 10-in-1 ---
    realtime_data = api_data.get("top10", [])
    if realtime_data:
        keywords_list = [item["keyword"] for item in realtime_data][:10]
        if len(keywords_list) == 10:
            line1_script = generate_line1_script(keywords_list, model)
            if line1_script:
                print("\n[=== 1라인 (실검 10-in-1) 대본 ===]")
                print(json.dumps(line1_script, indent=2, ensure_ascii=False))

                # ✅ 실시간 검색어 대본 저장
                with open(
                    "output/scripts/00_realtime_script.json",
                    "w",
                    encoding="utf-8",
                ) as f:
                    json.dump(line1_script, f, ensure_ascii=False, indent=2)
                print(
                    "✅ 실시간 검색어 대본 저장 완료: output/scripts/00_realtime_script.json"
                )
        else:
            print("[경고] 실검 키워드가 10개 미만이라 1라인 생성을 건너뜁니다.")
    else:
        print("[경고] 'top10' 데이터가 없어 1라인을 건너뜁니다.")

    # --- 2단계 (멀티 뉴스) 실행: 3-3-4 그룹으로 묶어서 3개 쇼츠 생성 ---
    popular_news_data = api_data.get("articles", [])
    if not popular_news_data:
        print("[경고] 'articles' 데이터가 없어 2라인(뉴스) 생성을 건너뜁니다.")
        print("\n--- 🚀 'main.py' 모든 작업 종료 ---")
        exit()

    # 상위 10개만 사용 (3-3-4)
    selected_news = popular_news_data[:10]
    print(f"\n--- 인기 뉴스 개수: {len(selected_news)} (최대 10개 사용) ---")

    groups = []
    if len(selected_news) >= 3:
        groups.append(selected_news[0:3])  # 1~3
    if len(selected_news) >= 6:
        groups.append(selected_news[3:6])  # 4~6
    if len(selected_news) > 6:
        groups.append(selected_news[6:10])  # 7~10 (3~4개)

    print(f"--- 뉴스 그룹 수: {len(groups)} (3-3-4 패턴) ---")

    multi_scripts_all = []
    group_index = 0

    for group in groups:
        group_index += 1
        print(f"\n[=== 뉴스 그룹 {group_index} 처리 시작 (크기 {len(group)}) ===]")

        news_list_for_prompt = []
        for item in group:
            raw_desc = item.get("desc", "") or ""
            link = item.get("link", "")

            # 🔥 여기서 스니펫 보강
            enriched = enrich_snippet_by_link(link, raw_desc)

            print("\n[DEBUG] 제목:", item.get("title", "")[:60])
            print("[DEBUG] 원본 desc:", raw_desc)
            print("[DEBUG] 보강된 snippet:", enriched[:300])

            news_list_for_prompt.append(
                {
                    "title": item.get("title", ""),
                    "snippet": enriched,
                }
            )

        # 멀티 뉴스 쇼츠 1개 생성
        multi_script = generate_multi_news_script(news_list_for_prompt, model)
        if multi_script:
            multi_scripts_all.append(multi_script)
            print("\n[=== 생성된 멀티 뉴스 대본 ===]")
            print(json.dumps(multi_script, indent=2, ensure_ascii=False))

            # ✅ 파일 저장
            fname = f"output/scripts/10_news_group_{group_index:02d}.json"
            with open(fname, "w", encoding="utf-8") as f:
                json.dump(multi_script, f, ensure_ascii=False, indent=2)
            print(f"✅ 멀티 뉴스 대본 저장: {fname}")

        # 무료 등급 RPM 고려 (필요 시 조절)
        time.sleep(2)

    print(f"\n--- 총 {len(multi_scripts_all)}개의 멀티 뉴스(3-3-4) 대본 생성 완료 ---")
    print("\n--- 🚀 'main.py' 모든 작업 완료 ---")