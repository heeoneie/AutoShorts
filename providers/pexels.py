import json
import os
import re
from pathlib import Path
from typing import Iterable, Optional

import requests

from config import CLIPS_DIR
from .base import BackgroundProvider

API_URL = "https://api.pexels.com/videos/search"


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


class PexelsProvider(BackgroundProvider):
    def __init__(self, api_key: Optional[str] = None, cache_dir: str = CLIPS_DIR):
        self.api_key = api_key or os.environ.get("PEXELS_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("PEXELS_API_KEY가 없습니다. .env에 설정하세요.")
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)

    def _search(self, query: str) -> list:
        """검색 결과를 query별로 JSON 캐시."""
        cache_file = self.cache / f"search_{_slug(query)}.json"
        if cache_file.exists():
            return json.loads(cache_file.read_text(encoding="utf-8"))
        r = requests.get(
            API_URL,
            headers={"Authorization": self.api_key},
            params={"query": query, "orientation": "portrait", "per_page": 15},
            timeout=10,
        )
        r.raise_for_status()
        videos = r.json().get("videos", [])
        cache_file.write_text(json.dumps(videos, ensure_ascii=False), encoding="utf-8")
        return videos

    @staticmethod
    def _best_file(video: dict) -> Optional[dict]:
        """1080 이하 중 가장 큰 mp4."""
        files = [
            f for f in video.get("video_files", [])
            if f.get("file_type") == "video/mp4" and (f.get("width") or 0) <= 1080
        ]
        return max(files, key=lambda f: f.get("width") or 0) if files else None

    def _download(self, video: dict) -> Optional[Path]:
        f = self._best_file(video)
        if not f:
            return None
        path = self.cache / f"pexels_{video['id']}.mp4"
        if path.exists():
            return path
        with requests.get(f["link"], stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(path, "wb") as out:
                for chunk in r.iter_content(1 << 16):
                    out.write(chunk)
        return path

    def fetch_clip(
        self,
        keywords: Iterable[str],
        min_duration: float,
        exclude: Iterable[str] = (),
    ) -> Optional[Path]:
        used = set(exclude)
        for kw in keywords:
            try:
                videos = self._search(kw)
            except requests.RequestException as e:
                print(f"[경고] Pexels 검색 실패 ({kw}): {e}")
                continue
            for v in videos:
                if v.get("duration", 0) < min_duration:
                    continue
                path = self.cache / f"pexels_{v['id']}.mp4"
                if str(path) in used:
                    continue
                try:
                    got = self._download(v)
                except requests.RequestException as e:
                    print(f"[경고] 다운로드 실패 ({v['id']}): {e}")
                    continue
                if got:
                    return got
        return None
