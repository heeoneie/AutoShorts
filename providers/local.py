import random
from pathlib import Path
from typing import Iterable, Optional

from .base import BackgroundProvider

EXTS = {".mp4", ".mov", ".m4v", ".webm"}


class LocalProvider(BackgroundProvider):
    """assets/clips/ 안의 영상을 사용. 파일명에 키워드가 들어 있으면 우선 매칭.

    예) assets/clips/money_coins.mp4 ← 키워드 'money'
    키워드 매칭이 없으면 아무 클립이나 (안 쓴 것 우선) 반환.
    """

    def __init__(self, root: str = "assets/clips"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def fetch_clip(
        self,
        keywords: Iterable[str],
        min_duration: float,
        exclude: Iterable[str] = (),
    ) -> Optional[Path]:
        used = set(exclude)
        files = [p for p in self.root.rglob("*") if p.suffix.lower() in EXTS]
        if not files:
            return None
        fresh = [p for p in files if str(p) not in used] or files
        for kw in keywords:
            hits = [p for p in fresh if kw.lower().replace(" ", "_") in p.stem.lower()]
            if hits:
                return random.choice(hits)
        return random.choice(fresh)
