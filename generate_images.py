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


def generate_news_images(news_dir: Path, output_dir: Path) -> int:
    """뉴스별 이미지 생성 (10장)"""
    print("\n[뉴스 이미지 생성]")

    news_files = sorted(glob(str(news_dir / "news_*.json")))

    if not news_files:
        print(f"  뉴스 파일 없음: {news_dir}")
        return 0

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    output_dir.mkdir(parents=True, exist_ok=True)

    success_count = 0

    for news_file in news_files:
        with open(news_file, "r", encoding="utf-8") as f:
            news = json.load(f)

        rank = news.get("rank", 0)
        title = news.get("title", "")
        image_url = news.get("image_url", "")

        print(f"\n  [뉴스 {rank:02d}] {title[:30]}...")

        filename = output_dir / f"news_{rank:02d}.png"

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
        fallback_prompt = f"""Create a dramatic vertical (9:16) news thumbnail for: "{title}"
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

    # 뉴스 이미지 생성
    if not args.keywords_only:
        news_count = generate_news_images(
            OUTPUT_DIR / "news",
            IMAGES_DIR / "news"
        )

    # 결과 출력
    print("\n" + "=" * 50)
    print("이미지 생성 완료!")
    print("=" * 50)
    print(f"키워드 이미지: {keyword_count}/10개")
    print(f"뉴스 이미지: {news_count}/10개")
    print(f"\n저장 위치: {IMAGES_DIR}")


if __name__ == "__main__":
    main()
