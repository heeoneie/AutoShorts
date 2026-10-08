from typing import Iterable, Optional
from pathlib import Path

from .base import BackgroundProvider


class ChainProvider(BackgroundProvider):
    """앞 provider가 None을 반환하면 다음 provider로 넘어감."""

    def __init__(self, providers):
        self.providers = providers

    def fetch_clip(self, keywords: Iterable[str], min_duration: float,
                   exclude: Iterable[str] = ()) -> Optional[Path]:
        keywords = list(keywords)
        for p in self.providers:
            clip = p.fetch_clip(keywords, min_duration, exclude)
            if clip:
                return clip
        return None


def _make(name: str) -> BackgroundProvider:
    if name == "pexels":
        from .pexels import PexelsProvider
        return PexelsProvider()
    if name == "local":
        from .local import LocalProvider
        return LocalProvider()
    if name == "ai_gen":
        from .ai_gen import AIGenProvider
        return AIGenProvider()
    raise ValueError(f"알 수 없는 BG_PROVIDER: {name}")


def get_provider(spec: str) -> BackgroundProvider:
    """'ai_gen,pexels'처럼 쉼표로 우선순위 체인 지정."""
    names = [n.strip() for n in spec.split(",") if n.strip()]
    providers = []
    for n in names:
        try:
            providers.append(_make(n))
        except Exception as e:
            print(f"[경고] provider '{n}' 사용 불가: {e}")
    if not providers:
        raise RuntimeError("사용 가능한 배경 provider가 없습니다.")
    return providers[0] if len(providers) == 1 else ChainProvider(providers)
