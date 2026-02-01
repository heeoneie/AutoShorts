# generate_script.py
"""
AI 대본 생성 모듈
- 키워드 1개 + 뉴스 10개 = 총 11개 스크립트 생성
"""

import os
import json
import time
from glob import glob
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")
PROMPTS_DIR = Path(__file__).parent / "prompts"
OUTPUT_DIR = Path(__file__).parent / "output"
SCRIPTS_DIR = OUTPUT_DIR / "scripts"


def load_prompt(prompt_file: str) -> str:
    """프롬프트 파일 로드"""
    path = PROMPTS_DIR / prompt_file
    if not path.exists():
        raise FileNotFoundError(f"프롬프트 없음: {path}")
    return path.read_text(encoding="utf-8")


def call_openai(content: str, system_prompt: str, model: str = DEFAULT_MODEL) -> dict:
    """OpenAI API 호출 (JSON 모드)"""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content}
                ],
                temperature=0.7,
                max_tokens=4000
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"    [API 오류] {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                raise


def generate_keyword_script(keywords_path: Path, output_path: Path) -> bool:
    """키워드 스크립트 생성 (1개)"""
    print("\n[키워드 스크립트 생성]")

    if not keywords_path.exists():
        print(f"  키워드 파일 없음: {keywords_path}")
        return False

    with open(keywords_path, "r", encoding="utf-8") as f:
        keywords = json.load(f)

    prompt = load_prompt("keyword_script.txt")
    content = json.dumps(keywords, ensure_ascii=False)

    print("  API 호출 중...")
    script = call_openai(content, prompt)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    print(f"  저장됨: {output_path}")
    return True


def generate_news_scripts(news_dir: Path, output_dir: Path) -> int:
    """뉴스 스크립트 생성 (10개)"""
    print("\n[뉴스 스크립트 생성]")

    prompt = load_prompt("news_script.txt")
    news_files = sorted(glob(str(news_dir / "news_*.json")))

    if not news_files:
        print(f"  뉴스 파일 없음: {news_dir}")
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    success_count = 0

    for news_file in news_files:
        filename = Path(news_file).stem  # news_01
        output_path = output_dir / f"script_{filename.replace('news_', 'news_')}.json"

        with open(news_file, "r", encoding="utf-8") as f:
            news_data = json.load(f)

        print(f"\n  [{news_data['rank']}/10] {news_data['title'][:30]}...")
        print("    API 호출 중...")

        try:
            content = json.dumps(news_data, ensure_ascii=False)
            script = call_openai(content, prompt)

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(script, f, ensure_ascii=False, indent=2)

            print(f"    저장됨: {output_path.name}")
            success_count += 1

        except Exception as e:
            print(f"    [실패] {e}")

    return success_count


def main():
    import argparse

    parser = argparse.ArgumentParser(description="AI 대본 생성 (11개)")
    parser.add_argument("--dry-run", action="store_true", help="API 호출 없이 확인")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY") and not args.dry_run:
        print("[에러] OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        return

    print("=" * 50)
    print("AI 대본 생성 (키워드 1개 + 뉴스 10개)")
    print("=" * 50)

    if args.dry_run:
        print("\n[DRY RUN 모드]")
        print(f"  키워드: {OUTPUT_DIR / 'keywords.json'}")
        print(f"  뉴스: {OUTPUT_DIR / 'news' / 'news_01~10.json'}")
        print(f"  출력: {SCRIPTS_DIR}")
        return

    # 키워드 스크립트 생성
    keyword_success = generate_keyword_script(
        OUTPUT_DIR / "keywords.json",
        SCRIPTS_DIR / "script_keyword.json"
    )

    # 뉴스 스크립트 생성
    news_count = generate_news_scripts(
        OUTPUT_DIR / "news",
        SCRIPTS_DIR
    )

    # 결과 출력
    print("\n" + "=" * 50)
    print("대본 생성 완료!")
    print("=" * 50)
    print(f"키워드 스크립트: {'성공' if keyword_success else '실패'}")
    print(f"뉴스 스크립트: {news_count}/10개 성공")
    print(f"\n저장 위치: {SCRIPTS_DIR}")


if __name__ == "__main__":
    main()
