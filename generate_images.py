# generate_images.py
"""
Google Gemini로 이미지 리컴포지션
- 원본 뉴스 이미지 → 세로형(9:16) 변환
- 키워드용 이미지 10장
- 뉴스용 이미지 10장
"""

import os
import json
import time
import requests
from io import BytesIO
from glob import glob
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

load_dotenv()

OUTPUT_DIR = Path(__file__).parent / "output"
IMAGES_DIR = OUTPUT_DIR / "images"

# Gemini Pro Image 모델 (세로 비율 지원)
IMAGE_MODEL = "gemini-3-pro-image-preview"


def download_image(url: str) -> bytes | None:
    """URL에서 이미지 다운로드"""
    if not url:
        return None

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        print(f"    [다운로드 실패] {e}")
        return None


def recompose_image(source_image: bytes, prompt: str, filename: str, client: genai.Client) -> bool:
    """원본 이미지를 기반으로 세로형 이미지 생성"""
    try:
        # PIL로 이미지 로드
        img = Image.open(BytesIO(source_image))

        # Gemini에 이미지와 프롬프트 전달
        response = client.models.generate_content(
            model=IMAGE_MODEL,
            contents=[
                img,
                prompt
            ],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            )
        )

        # 응답에서 이미지 추출
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    image_data = part.inline_data.data
                    with open(filename, "wb") as f:
                        f.write(image_data)
                    return True

        print(f"    [에러] 이미지가 생성되지 않았습니다.")
        return False

    except Exception as e:
        print(f"    [에러] {e}")
        return False


def generate_image_from_prompt(prompt: str, filename: str, client: genai.Client) -> bool:
    """텍스트 프롬프트만으로 이미지 생성 (폴백용)"""
    try:
        response = client.models.generate_content(
            model=IMAGE_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            )
        )

        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    image_data = part.inline_data.data
                    with open(filename, "wb") as f:
                        f.write(image_data)
                    return True

        print(f"    [에러] 이미지가 생성되지 않았습니다.")
        return False

    except Exception as e:
        print(f"    [에러] {e}")
        return False


RECOMPOSE_PROMPT = """Based on this source image, create a new vertical (9:16 ratio) image for a YouTube Shorts news thumbnail.

Requirements:
- Maintain the core subject and meaning of the original image
- Recompose for vertical 9:16 aspect ratio
- Enhance with dramatic, cinematic lighting
- Make it eye-catching and professional
- NO text, NO words, NO letters in the image
- Keep the news/journalism aesthetic
- High contrast and vibrant colors"""


def generate_keyword_images(keywords_path: Path, output_dir: Path) -> int:
    """키워드별 이미지 생성 (10장)"""
    print("\n[키워드 이미지 생성]")

    if not keywords_path.exists():
        print(f"  파일 없음: {keywords_path}")
        return 0

    with open(keywords_path, "r", encoding="utf-8") as f:
        keywords = json.load(f)

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    output_dir.mkdir(parents=True, exist_ok=True)

    success_count = 0

    for item in keywords:
        rank = item["rank"]
        keyword = item["keyword"]
        image_url = item.get("image_url", "")

        print(f"\n  [{rank}/10] {keyword}")

        filename = output_dir / f"keyword_{rank:02d}.png"

        if image_url:
            # 원본 이미지 다운로드 및 리컴포지션
            print(f"    원본 이미지 다운로드 중...")
            source_image = download_image(image_url)

            if source_image:
                print(f"    리컴포지션 중...")
                if recompose_image(source_image, RECOMPOSE_PROMPT, str(filename), client):
                    print(f"    저장됨: {filename.name}")
                    success_count += 1
                    time.sleep(1)
                    continue

        # 폴백: 텍스트 프롬프트로 생성
        print(f"    텍스트 프롬프트로 생성 중...")
        fallback_prompt = f"""Create a dramatic vertical (9:16) news thumbnail for: "{keyword}"
- Bold, cinematic composition
- NO text in image
- Professional news aesthetic
- High contrast, vibrant colors"""

        if generate_image_from_prompt(fallback_prompt, str(filename), client):
            print(f"    저장됨: {filename.name}")
            success_count += 1
            time.sleep(1)
        else:
            print(f"    실패")

    return success_count


SCRIPTS_DIR = OUTPUT_DIR / "scripts"
VIDEO_DURATION = 30  # 영상 길이 (초)


def plan_image_scenes_with_ai(script_data: dict) -> list[dict]:
    """GPT-4로 대본 분석 후 이미지 씬 계획 생성"""
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    title = script_data.get("news_title", script_data.get("title", ""))
    script_parts = script_data.get("script", [])

    # 대본 텍스트 구성
    script_text = ""
    for part in script_parts:
        part_type = part.get("type", "")
        text = part.get("text", "")
        script_text += f"[{part_type}] {text}\n"

    system_prompt = """You are a visual director for YouTube Shorts news videos.
Given a script for a 30-second news video, plan the visual scenes.

Rules:
- Each image will be shown for 3-5 seconds with Ken Burns effect
- Determine the optimal number of images (typically 5-10 for 30 seconds)
- Each scene should match the script's narrative flow
- Consider visual variety and storytelling

Output JSON format:
{
  "total_images": <number>,
  "scenes": [
    {"seq": 1, "duration": 4, "description": "Detailed scene description for image generation"},
    ...
  ]
}

IMPORTANT: Output valid JSON only, no explanation."""

    user_prompt = f"""Plan visual scenes for this 30-second news video:

Title: {title}

Script:
{script_text}

Create a scene plan with appropriate number of images."""

    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview"),
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        result = json.loads(response.choices[0].message.content)
        return result.get("scenes", [])
    except Exception as e:
        print(f"    [AI 씬 계획 실패] {e}")
        # 폴백: 기본 5장
        return [
            {"seq": 1, "duration": 5, "description": f"Opening scene for: {title}"},
            {"seq": 2, "duration": 6, "description": f"Main point illustration"},
            {"seq": 3, "duration": 6, "description": f"Development and context"},
            {"seq": 4, "duration": 6, "description": f"Impact and reaction"},
            {"seq": 5, "duration": 7, "description": f"Closing summary scene"},
        ]


def generate_news_images(news_dir: Path, output_dir: Path) -> int:
    """뉴스별 이미지 생성 (AI가 씬 개수 결정)"""
    print("\n[뉴스 이미지 생성 - AI 씬 계획]")

    script_files = sorted(glob(str(SCRIPTS_DIR / "script_news_*.json")))

    if not script_files:
        print(f"  스크립트 없음: {SCRIPTS_DIR}")
        return 0

    gemini_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    output_dir.mkdir(parents=True, exist_ok=True)

    total_success = 0

    for script_file in script_files:
        with open(script_file, "r", encoding="utf-8") as f:
            script_data = json.load(f)

        num = Path(script_file).stem.split("_")[-1]
        title = script_data.get("news_title", script_data.get("title", ""))

        print(f"\n  [뉴스 {num}] {title[:30]}...")

        # AI로 씬 계획 생성
        print(f"    GPT-4로 씬 계획 생성 중...")
        scenes = plan_image_scenes_with_ai(script_data)
        total_scenes = len(scenes)
        print(f"    → {total_scenes}장 이미지 계획됨")

        # 씬 계획 저장 (나중에 영상 합성 시 사용)
        news_output_dir = output_dir / f"news_{num}"
        news_output_dir.mkdir(parents=True, exist_ok=True)

        with open(news_output_dir / "scenes.json", "w", encoding="utf-8") as f:
            json.dump({"title": title, "scenes": scenes}, f, ensure_ascii=False, indent=2)

        # 원본 이미지 다운로드
        news_file = news_dir / f"news_{num}.json"
        source_image = None
        if news_file.exists():
            with open(news_file, "r", encoding="utf-8") as f:
                news_data = json.load(f)
                image_url = news_data.get("image_url", "")
                if image_url:
                    print(f"    원본 이미지 다운로드 중...")
                    source_image = download_image(image_url)

        news_success = 0

        for scene in scenes:
            seq = scene.get("seq", 0)
            description = scene.get("description", "")
            filename = news_output_dir / f"{seq:02d}.png"

            print(f"    [{seq}/{total_scenes}] {description[:40]}...")

            full_prompt = f"""{description}

News Title: {title}

Requirements:
- Vertical 9:16 aspect ratio for YouTube Shorts
- Dramatic, cinematic composition
- NO text, NO words, NO letters in the image
- Professional news/documentary aesthetic
- High contrast, vibrant colors"""

            if source_image:
                if recompose_image(source_image, full_prompt, str(filename), gemini_client):
                    print(f"      저장됨: {filename.name}")
                    news_success += 1
                    time.sleep(1)
                    continue

            if generate_image_from_prompt(full_prompt, str(filename), gemini_client):
                print(f"      저장됨: {filename.name}")
                news_success += 1
                time.sleep(1)
            else:
                print(f"      실패")

        print(f"    완료: {news_success}/{total_scenes}장")
        total_success += news_success

    return total_success


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Gemini 이미지 리컴포지션")
    parser.add_argument("--keywords-only", action="store_true", help="키워드 이미지만 생성")
    parser.add_argument("--news-only", action="store_true", help="뉴스 이미지만 생성")
    parser.add_argument("--dry-run", action="store_true", help="실행 없이 확인")
    args = parser.parse_args()

    if not os.getenv("GOOGLE_API_KEY"):
        print("[에러] GOOGLE_API_KEY 환경변수가 설정되지 않았습니다.")
        return

    print("=" * 50)
    print("Gemini 이미지 리컴포지션")
    print("=" * 50)

    if args.dry_run:
        print("\n[DRY RUN 모드]")
        print(f"  키워드: {OUTPUT_DIR / 'keywords.json'}")
        print(f"  뉴스: {OUTPUT_DIR / 'news'}")
        print(f"  출력: {IMAGES_DIR}")
        return

    keyword_count = 0
    news_count = 0

    # 키워드 이미지 생성
    if not args.news_only:
        keyword_count = generate_keyword_images(
            OUTPUT_DIR / "keywords.json",
            IMAGES_DIR / "keywords"
        )

    # 뉴스 이미지 생성 (대본 기반)
    if not args.keywords_only:
        news_count = generate_news_images(
            OUTPUT_DIR / "news",  # 원본 이미지 URL용
            IMAGES_DIR / "news"
        )

    # 결과 출력
    print("\n" + "=" * 50)
    print("이미지 생성 완료!")
    print("=" * 50)
    print(f"키워드 이미지: {keyword_count}/10개")
    print(f"뉴스 이미지: {news_count}개 (AI가 씬 개수 결정)")
    print(f"\n저장 위치: {IMAGES_DIR}")


if __name__ == "__main__":
    main()
