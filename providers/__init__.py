# providers/__init__.py
from abc import ABC, abstractmethod


class VisionProvider(ABC):
    """Base class for vision providers."""

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def read_image(self, image_path: str) -> dict:
        """Returns {"measured_angle": float}"""


PROVIDERS: dict[str, type] = {}


def register_provider(name: str):
    def decorator(cls):
        PROVIDERS[name] = cls
        return cls
    return decorator


def get_provider(name: str, config: dict) -> VisionProvider:
    if name not in PROVIDERS:
        raise ValueError(
            f"Unknown provider: {name}. Available: {list(PROVIDERS.keys())}"
        )
    return PROVIDERS[name](config)
