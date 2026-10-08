import hashlib
import json
import os
import time
from pathlib import Path
from typing import Iterable, Optional

import requests

from config import CLIPS_DIR
from .base import BackgroundProvider

API = "https://api.replicate.com/v1"
# 실행당 약 $0.05 (lightricks/ltx-video, 2026-10 기준 Replicate 표기)
DEFAULT_MODEL = "lightricks/ltx-video"
# 모델마다 입력 파라미터 이름이 다르므로 AI_VIDEO_INPUT(JSON)으로 덮어쓸 수 있음
DEFAULT_INPUT = {"width": 512, "height": 768, "length": 97}  # 세로, 약 4초


def build_prompt(keywords: Iterable[str]) -> str:
    kws = ", ".join(k for k in keywords if k)
    return (f"{kws}, cinematic, dynamic camera movement, vertical video, "
            "abstract and conceptual, no text, no logos, no recognizable people")


class AIGenProvider(BackgroundProvider):
    """Replicate 호스팅 API로 배경 클립을 생성.

    비용 보호:
      - AI_MAX_CLIPS(기본 6): 한 번 실행에서 새로 생성할 최대 개수. 초과 시 None 반환
        → 체인의 다음 provider(pexels/local/단색)로 넘어감
      - 프롬프트 해시 기준 캐시: 같은 프롬프트는 다시 생성하지 않음
    exclude는 무시한다. 클립은 문장 단위로 생성되고, 같은 문장의 여러 장면이
    렌더 단계의 랜덤 시작 지점으로 재사용된다.
    """

    def __init__(self, cache_dir: str = CLIPS_DIR):
        self.token = os.environ.get("REPLICATE_API_TOKEN", "")
        if not self.token:
            raise RuntimeError("REPLICATE_API_TOKEN이 없습니다. .env에 설정하세요.")
        self.model = os.environ.get("AI_VIDEO_MODEL", DEFAULT_MODEL)
        self.extra_input = {**DEFAULT_INPUT, **json.loads(os.environ.get("AI_VIDEO_INPUT", "{}"))}
        self.max_new = int(os.environ.get("AI_MAX_CLIPS", "6"))
        self.generated = 0
        self.cache = Path(cache_dir) / "ai"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def _cache_path(self, prompt: str) -> Path:
        h = hashlib.sha1(f"{self.model}|{prompt}|{self.extra_input}".encode()).hexdigest()[:16]
        return self.cache / f"ai_{h}.mp4"

    def _generate(self, prompt: str) -> str:
        r = requests.post(
            f"{API}/models/{self.model}/predictions",
            headers={**self.headers, "Prefer": "wait=60"},
            json={"input": {"prompt": prompt, **self.extra_input}},
            timeout=90,
        )
        r.raise_for_status()
        pred = r.json()
        deadline = time.time() + 300
        while pred["status"] not in ("succeeded", "failed", "canceled"):
            if time.time() > deadline:
                raise TimeoutError("영상 생성 시간 초과")
            time.sleep(3)
            pred = requests.get(pred["urls"]["get"], headers=self.headers, timeout=30).json()
        if pred["status"] != "succeeded":
            raise RuntimeError(f"생성 실패: {pred.get('error')}")
        out = pred["output"]
        return out[0] if isinstance(out, list) else out

    def fetch_clip(
        self,
        keywords: Iterable[str],
        min_duration: float,
        exclude: Iterable[str] = (),
    ) -> Optional[Path]:
        prompt = build_prompt(keywords)
        path = self._cache_path(prompt)
        if path.exists():
            return path
        if self.generated >= self.max_new:
            return None  # 비용 상한 도달
        try:
            print(f"  💸 AI 영상 생성 {self.generated + 1}/{self.max_new} (약 $0.05): {prompt[:60]}")
            url = self._generate(prompt)
            with requests.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(path, "wb") as f:
                    for chunk in r.iter_content(1 << 16):
                        f.write(chunk)
        except Exception as e:
            print(f"[경고] AI 영상 생성 실패: {e}")
            return None
        self.generated += 1
        return path
