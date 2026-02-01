# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AutoShorts는 실시간 트렌딩 뉴스를 자동으로 수집하여 숏폼 영상 콘텐츠를 생성하는 파이프라인입니다.

## Pipeline

```
main.py → generate_script.py → tts_generate.py → make_videos.py
```

1. **main.py**: signal.bz API에서 실시간 뉴스 Top 10 수집, 기사 본문 스크래핑, 3-3-4 그룹 분할
2. **generate_script.py**: OpenAI GPT-4로 뉴스 그룹을 대본 JSON으로 변환
3. **tts_generate.py**: 스크립트 JSON을 읽어 gTTS로 음성 생성 + SRT 자막 파일 생성
4. **make_videos.py**: FFmpeg로 오디오+자막 기반 미리보기 영상 생성

## Commands

```bash
# 전체 파이프라인 실행 (권장)
python pipeline.py

# 대본 검토 후 진행
python pipeline.py --review

# 특정 단계부터 시작
python pipeline.py --start generate

# 개별 스크립트 실행
python main.py              # 뉴스 수집
python generate_script.py   # AI 대본 생성
python tts_generate.py      # TTS 생성
python make_videos.py       # 영상 생성
```

## Setup

```bash
# 의존성 설치
pip install -r requirements.txt

# API 키 설정
cp .env.example .env
# .env 파일에서 OPENAI_API_KEY 설정
```

## Dependencies

- Python: `requests`, `beautifulsoup4`, `gtts`, `openai`, `python-dotenv`
- System: `ffmpeg` (영상 생성에 필요)

## Output Structure

```
output/
├── realtime_top10_keywords.json  # 실시간 검색어 Top 10
├── news_top10.json               # 뉴스 Top 10 (rank, title, url, snippet)
├── news_group_01.json            # 뉴스 1~3위
├── news_group_02.json            # 뉴스 4~6위
├── news_group_03.json            # 뉴스 7~10위
├── scripts/                      # AI 생성 대본 JSON
├── audio/                        # TTS MP3 파일
├── subtitles/                    # SRT 자막 파일
└── videos/                       # 미리보기 MP4 영상
```

## Script JSON Format

`output/scripts/*.json` 파일 형식:
```json
{
  "title": "영상 제목",
  "script": [
    {"type": "hook", "text": "오프닝 훅"},
    {"type": "body", "rank": 1, "text": "본문 내용"},
    {"type": "closing", "text": "클로징 멘트"}
  ]
}
```

## Notes

- 기사 본문 추출: Firecrawl API 우선, 실패 시 BeautifulSoup 폴백
- 자막 타이밍은 글자 수 기반 추정 (CHARS_PER_SEC = 9.0)
- 영상 해상도: 1080x1920 (세로형 숏폼)
- AI 대본 생성은 `prompts/script_system.txt` 프롬프트 사용
