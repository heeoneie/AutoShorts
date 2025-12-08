# config.py
"""Configuration constants for AutoShorts news scraper"""

# API Configuration
SIGNAL_API_URL = "https://api.signal.bz/news/realtime"
SIGNAL_REFERER = "https://www.signal.bz/"

# Request Headers
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.google.com/",
}

API_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36"
    ),
    "Referer": SIGNAL_REFERER,
}

# Request Timeouts
API_TIMEOUT = 5
ARTICLE_TIMEOUT = 7

# Output Directories
OUTPUT_DIR = "output"
REALTIME_KEYWORDS_FILE = "output/realtime_top10_keywords.json"
NEWS_TOP10_FILE = "output/news_top10.json"
NEWS_GROUP_FILE_PATTERN = "output/news_group_{:02d}.json"

# News Processing
TOP_NEWS_COUNT = 10
NEWS_GROUP_SIZES = [3, 3, 4]  # 3-3-4 grouping pattern

# Nate News Parser Patterns
NATE_END_PATTERNS = [
    "MBN 화제뉴스",
    "네이버에서 'MBN뉴스'",
    "Make a Better Next, MBN",
    "MBN 무료 고화질 온에어 서비스 GO!",
    "MBN(www.mbn.co.kr)",
    "무단전재 및 재배포 금지",
    "< Copyright",
    "Copyright ⓒ",
]
