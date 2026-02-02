# pipeline.py
"""
AutoShorts 파이프라인 오케스트레이션
- 뉴스 수집 → 대본 생성 → TTS → 영상 생성
"""

import os
import sys
import subprocess
from pathlib import Path
from enum import Enum
from glob import glob
from typing import List, Optional

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent
OUTPUT_DIR = PROJECT_ROOT / "output"


class Stage(Enum):
    """파이프라인 단계"""
    SCRAPE = "scrape"
    GENERATE = "generate"
    TTS = "tts"
    VIDEO = "video"


STAGE_ORDER = [Stage.SCRAPE, Stage.GENERATE, Stage.TTS, Stage.VIDEO]

STAGE_SCRIPTS = {
    Stage.SCRAPE: "main.py",
    Stage.GENERATE: "generate_script.py",
    Stage.TTS: "tts_generate.py",
    Stage.VIDEO: "make_videos.py",
}

STAGE_NAMES = {
    Stage.SCRAPE: "뉴스 수집",
    Stage.GENERATE: "대본 생성",
    Stage.TTS: "TTS 생성",
    Stage.VIDEO: "영상 생성",
}


class PipelineError(Exception):
    """파이프라인 에러"""
    pass


def check_stage_outputs(stage: Stage) -> bool:
    """단계별 출력물 확인"""
    if stage == Stage.SCRAPE:
        pattern = str(OUTPUT_DIR / "news_group_*.json")
        return len(glob(pattern)) > 0

    elif stage == Stage.GENERATE:
        pattern = str(OUTPUT_DIR / "scripts" / "*.json")
        return len(glob(pattern)) > 0

    elif stage == Stage.TTS:
        audio_pattern = str(OUTPUT_DIR / "audio" / "*.mp3")
        srt_pattern = str(OUTPUT_DIR / "subtitles" / "*.srt")
        return len(glob(audio_pattern)) > 0 and len(glob(srt_pattern)) > 0

    elif stage == Stage.VIDEO:
        pattern = str(OUTPUT_DIR / "videos" / "*.mp4")
        return len(glob(pattern)) > 0

    return False


def run_stage(stage: Stage, dry_run: bool = False) -> bool:
    """
    단계 실행

    Args:
        stage: 실행할 단계
        dry_run: True면 실행 없이 시뮬레이션

    Returns:
        성공 여부
    """
    script_name = STAGE_SCRIPTS[stage]
    script_path = PROJECT_ROOT / script_name
    stage_name = STAGE_NAMES[stage]

    print(f"\n{'=' * 50}")
    print(f"[{stage.value.upper()}] {stage_name}")
    print(f"{'=' * 50}")

    if not script_path.exists():
        print(f"[에러] 스크립트를 찾을 수 없습니다: {script_path}")
        return False

    if dry_run:
        print(f"[DRY RUN] python {script_path}")
        return True

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(PROJECT_ROOT),
            check=True
        )
        return True

    except subprocess.CalledProcessError as e:
        print(f"[에러] {stage_name} 실패 (exit code: {e.returncode})")
        return False

    except Exception as e:
        print(f"[에러] {stage_name} 실행 중 예외 발생: {e}")
        return False


def wait_for_review() -> bool:
    """
    사용자 검토 대기

    Returns:
        True: 계속 진행
        False: 중단
    """
    scripts_dir = OUTPUT_DIR / "scripts"
    scripts = sorted(glob(str(scripts_dir / "*.json")))

    print("\n" + "=" * 50)
    print("=== 대본 검토 ===")
    print("=" * 50)

    if not scripts:
        print("[경고] 생성된 대본이 없습니다.")
        return False

    print("\n생성된 대본 파일:")
    for i, script in enumerate(scripts, 1):
        print(f"  {i}. {Path(script).name}")

    print("\n대본을 검토하세요.")
    print(f"  위치: {scripts_dir}")
    print("")

    while True:
        try:
            response = input("계속하려면 Enter, 중단하려면 'q' 입력: ").strip().lower()

            if response == "":
                print("\n계속 진행합니다...")
                return True
            elif response == "q":
                print("\n파이프라인을 중단합니다.")
                return False
            else:
                print("Enter 또는 'q'를 입력하세요.")

        except KeyboardInterrupt:
            print("\n\n파이프라인을 중단합니다.")
            return False


def run_pipeline(
    start_stage: Stage = Stage.SCRAPE,
    end_stage: Stage = Stage.VIDEO,
    review: bool = False,
    skip_existing: bool = False,
    dry_run: bool = False
) -> bool:
    """
    파이프라인 실행

    Args:
        start_stage: 시작 단계
        end_stage: 종료 단계
        review: 대본 생성 후 검토 대기
        skip_existing: 출력물이 있으면 스킵
        dry_run: 실행 없이 시뮬레이션

    Returns:
        성공 여부
    """
    print("\n" + "=" * 50)
    print("=== AutoShorts 파이프라인 ===")
    print("=" * 50)

    start_idx = STAGE_ORDER.index(start_stage)
    end_idx = STAGE_ORDER.index(end_stage)

    stages_to_run = STAGE_ORDER[start_idx:end_idx + 1]

    print(f"\n실행 단계: {' → '.join(STAGE_NAMES[s] for s in stages_to_run)}")
    if review:
        print("대본 검토: 활성화")
    if skip_existing:
        print("기존 출력물 스킵: 활성화")
    if dry_run:
        print("드라이런 모드: 활성화")
    print("")

    for stage in stages_to_run:
        # 기존 출력물 확인
        if skip_existing and check_stage_outputs(stage):
            print(f"\n[{stage.value.upper()}] {STAGE_NAMES[stage]} - 출력물 존재, 스킵")
            continue

        # 단계 실행
        success = run_stage(stage, dry_run=dry_run)

        if not success:
            print(f"\n[실패] {STAGE_NAMES[stage]} 단계에서 중단됨")
            return False

        # 대본 생성 후 검토
        if stage == Stage.GENERATE and review and not dry_run:
            if not wait_for_review():
                return False

    print("\n" + "=" * 50)
    print("=== 파이프라인 완료 ===")
    print("=" * 50)

    # 결과 요약
    print("\n생성된 파일:")
    for stage in stages_to_run:
        if check_stage_outputs(stage):
            print(f"  {STAGE_NAMES[stage]}")

    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="AutoShorts 파이프라인",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python pipeline.py                    # 전체 파이프라인 실행
  python pipeline.py --review           # 대본 검토 후 진행
  python pipeline.py --start generate   # 대본 생성부터 시작
  python pipeline.py --end tts          # TTS까지만 실행
  python pipeline.py --dry-run          # 시뮬레이션
        """
    )

    parser.add_argument(
        "--start",
        choices=["scrape", "generate", "tts", "video"],
        default="scrape",
        help="시작 단계 (기본: scrape)"
    )
    parser.add_argument(
        "--end",
        choices=["scrape", "generate", "tts", "video"],
        default="video",
        help="종료 단계 (기본: video)"
    )
    parser.add_argument(
        "--review",
        action="store_true",
        help="대본 생성 후 검토 대기"
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="출력물이 있는 단계 스킵"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실행 없이 시뮬레이션"
    )

    args = parser.parse_args()

    start_stage = Stage(args.start)
    end_stage = Stage(args.end)

    # 시작 단계가 종료 단계보다 뒤면 에러
    if STAGE_ORDER.index(start_stage) > STAGE_ORDER.index(end_stage):
        print("[에러] 시작 단계가 종료 단계보다 뒤에 있습니다.")
        sys.exit(1)

    success = run_pipeline(
        start_stage=start_stage,
        end_stage=end_stage,
        review=args.review,
        skip_existing=args.skip_existing,
        dry_run=args.dry_run
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
