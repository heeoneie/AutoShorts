import os
from pathlib import Path

ROOT = Path(__file__).parent


def load_env(path: Path = ROOT / ".env") -> None:
    """간단한 .env 로더 (이미 설정된 환경변수는 덮어쓰지 않음)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()

SCRIPTS_DIR = "output/scripts"
AUDIO_DIR = "output/audio"
TIMELINE_DIR = "output/timeline"
SUBS_DIR = "output/subtitles"
CLIPS_DIR = "output/clips"
OUT_DIR = "output/videos"

VIDEO_W, VIDEO_H, FPS = 1080, 1920, 30
SCENE_SEC = 1.5          # 배경 영상 전환 주기
TTS_TEMPO = 1.12         # gTTS는 느리므로 약간 빠르게
BG_PROVIDER = os.environ.get("BG_PROVIDER", "pexels")
