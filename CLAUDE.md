# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AutoShorts is a Korean news shorts video automation system that:
1. Scrapes real-time trending news from signal.bz API
2. Groups news articles (3-3-4 structure: top 10 split into groups of 3, 3, and 4 articles)
3. Generates dramatic narration scripts optimized for short-form video content
4. Creates TTS audio from scripts using gTTS
5. Generates SRT subtitle files with timing
6. Produces preview videos combining audio and subtitles

## Core Pipeline

The system follows a strict 3-stage pipeline:

### Stage 1: News Scraping & Grouping (`main.py`)
- Fetches trending keywords (top10) and news articles from signal.bz API
- Scrapes full article content from news URLs
- Special handling for news.nate.com (custom body extraction)
- Outputs:
  - `output/realtime_top10_keywords.json` - Real-time search keywords
  - `output/news_top10.json` - Top 10 news with snippets
  - `output/news_group_01.json`, `news_group_02.json`, `news_group_03.json` - 3-3-4 grouping

### Stage 2: TTS & Subtitle Generation (`tts_generate.py`)
- Reads script JSON files from `output/scripts/`
- Flattens script structure: opening → content (by rank) → closing
- Generates Korean TTS audio using gTTS
- Creates SRT subtitle files with estimated timing (9 chars/sec default)
- Outputs:
  - `output/audio/{filename}.mp3` - TTS audio files
  - `output/subtitles/{filename}.srt` - Subtitle files

### Stage 3: Video Assembly (`make_videos.py`)
- Combines audio + subtitles into preview videos
- Uses FFmpeg to create black background (1080x1920) vertical videos
- Outputs:
  - `output/videos/{filename}_preview.mp4` - Preview videos

## Script JSON Structure

Scripts in `output/scripts/` follow this format:
```json
{
  "title": "Video title",
  "hashtags": ["#tag1", "#tag2"],
  "script": [
    {
      "type": "hook" | "opening" | "body" | "content" | "closing",
      "text": "Narration text",
      "rank": 1  // Optional, used for ordering body/content sections
    }
  ]
}
```

## Script Generation Prompt

The `script_prompt.md` file defines the narration style for scripts:
- **Tone**: Aggressive, direct, crisis-driven ("멱살 잡는 톤")
- **Structure**: 14 CUT segments (0-6s hook, rising action, analysis, future impact, CTA)
- **Duration**: 60-90 seconds total
- **Per CUT**: 2-3 short sentences (1-7 sec each)
- **Image Keywords**: Each sentence includes 3-5 English keywords for stock image search (Freepik/Shutterstock/iStock compatible)

## Development Commands

### Run the complete pipeline:
```bash
# Stage 1: Scrape news and generate groups
python main.py

# Stage 2: Generate TTS audio and subtitles
python tts_generate.py

# Stage 3: Create preview videos (requires FFmpeg)
python make_videos.py
```

### Dependencies:
```bash
pip install beautifulsoup4 requests gtts
# FFmpeg must be installed separately for video generation
```

## Code Architecture

### Module Overview

The Stage 1 codebase is organized into focused modules:

**`main.py`** - Entry point and pipeline orchestration
- Coordinates the entire news scraping workflow
- Minimal logic, delegates to specialized modules
- Handles high-level flow control and output

**`config.py`** - Configuration and constants
- API URLs and endpoints
- HTTP headers and timeouts
- Output file paths and naming patterns
- News grouping configuration (3-3-4 pattern)
- Nate news parser patterns

**`scraper.py`** - Web scraping functionality
- `fetch_signal_api()`: Fetches data from signal.bz realtime API
- `fetch_article_content()`: Retrieves and extracts content from news URLs
- Handles HTTP requests with proper error handling

**`parser.py`** - HTML parsing utilities
- `extract_article_snippet()`: Multi-strategy content extraction from HTML
- `extract_nate_body()`: Custom parser for news.nate.com articles
- `clean_text()`: Text normalization utility
- Fallback strategies: Nate custom → og:description → meta description → first `<p>`

**`processor.py`** - News processing and grouping
- `build_news_top10()`: Processes top 10 articles with full content
- `group_news_3_3_4()`: Splits into three groups: [0:3], [3:6], [6:10]
- `print_groups_for_prompt()`: Formats output for ChatGPT prompts

**`utils.py`** - Utility functions
- `save_json()`: JSON file output with proper encoding
- `ensure_output_dir()`: Directory creation helper
- `extract_keywords()`: Keyword list extraction from API data

### TTS Generation (`tts_generate.py`)
- `flatten_script_for_narration()`: Orders script segments properly
- `estimate_duration()`: Calculates subtitle timing (min 1.2s, max 5.0s per line)
- `build_srt()`: Generates SRT format with 0.15s gaps between subtitles
- Uses gTTS with Korean language (`lang='ko'`)

### Video Assembly (`make_videos.py`)
- Minimal script that pairs audio + subtitles
- Creates vertical format videos (1080x1920) for mobile shorts
- Requires FFmpeg command-line tool

## Key Configuration Values

### TTS Settings (`tts_generate.py`):
- `CHARS_PER_SEC = 9.0` - Korean character reading speed for subtitle timing
- `LANG = "ko"` - Korean language for gTTS
- `VOICE_SLOW = False` - Normal speech speed

### Video Settings (`make_videos.py`):
- Resolution: `1080x1920` (vertical/portrait)
- Background: Black (`color=c=black`)
- Subtitle style: Fontsize=36, white color, outline and shadow

## Important Implementation Details

1. **Nate News Extraction**: The system has custom logic to handle news.nate.com articles which require special parsing to skip photo captions, bylines, and footer content.

2. **Script Type Flexibility**: Scripts accept both `opening`/`hook`, `body`/`content`, and `closing` types interchangeably for backward compatibility.

3. **Audio-First Approach**: Subtitle timing is estimated from text length, not from actual audio duration. For production use, consider using actual audio duration for precise timing.

4. **Output Directory Structure**:
   ```
   output/
   ├── realtime_top10_keywords.json
   ├── news_top10.json
   ├── news_group_01.json, news_group_02.json, news_group_03.json
   ├── scripts/*.json
   ├── audio/*.mp3
   ├── subtitles/*.srt
   └── videos/*_preview.mp4
   ```

## Language & Locale

- All narration scripts are in Korean
- Script prompt (`script_prompt.md`) is in Korean
- Image keywords must be in English for stock photo search compatibility
- Console output and comments are in Korean
