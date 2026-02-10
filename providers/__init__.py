# providers/__init__.py
from abc import ABC, abstractmethod
import json
import re


class VisionProvider(ABC):
    """Base class for LLM vision providers."""

    PROMPT = (
        "Look at this scatter plot image. Extract exactly one value:\n"
        "The GREEN angle measurement drawn on the plot near the intersection\n"
        "of the blue and red lines. It is a green number followed by a degree\n"
        "symbol (e.g., 90.55° or 88.94°). This value is typically between\n"
        "80° and 100°. Read ALL digits carefully — do not drop the leading\n"
        "digits. This is NOT the Twist value from the title.\n"
        "\n"
        "Return JSON only: "
        '{"measured_angle": 90.89}'
    )

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def read_image(self, image_path: str) -> dict:
        """Returns {"measured_angle": float}"""

    def parse_response(self, text: str) -> dict:
        """Extract JSON from LLM response text."""
        match = re.search(r"\{[^}]+\}", text)
        if not match:
            raise ValueError(f"No JSON found in response: {text[:200]}")
        data = json.loads(match.group())
        if "measured_angle" not in data:
            raise ValueError(
                f"Missing required field 'measured_angle'. Got {set(data.keys())}"
            )
        return {
            "measured_angle": float(data["measured_angle"]),
        }


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
