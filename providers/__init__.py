from .base import BackgroundProvider


def get_provider(name: str) -> BackgroundProvider:
    if name == "pexels":
        from .pexels import PexelsProvider
        return PexelsProvider()
    if name == "local":
        from .local import LocalProvider
        return LocalProvider()
    raise ValueError(f"알 수 없는 BG_PROVIDER: {name}")
