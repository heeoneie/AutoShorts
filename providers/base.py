from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, Optional


class BackgroundProvider(ABC):
    """배경 영상 공급자. Pexels / 로컬 클립 / AI 생성 등으로 교체 가능."""

    @abstractmethod
    def fetch_clip(
        self,
        keywords: Iterable[str],
        min_duration: float,
        exclude: Iterable[str] = (),
    ) -> Optional[Path]:
        """키워드에 맞는 세로 영상 로컬 경로 반환. 못 찾으면 None.

        exclude: 이미 쓴 클립의 경로(str). 같은 영상 반복을 피하는 데 사용.
        """
