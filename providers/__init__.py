# providers/__init__.py
from abc import ABC, abstractmethod
import json
import re


class VisionProvider(ABC):
    """Base class for LLM vision providers."""

    PROMPT = (
        "Look at this plot image. Extract exactly three values:\n"
        '1. The "Pile" number from the title (e.g., "Pile: 2787.0" -> 2787)\n'
        "2. The angle measurement annotation drawn by the human (a green number\n"
        '   followed by a degree symbol that is NOT part of the "Twist:" label)\n'
        '3. The current "Twist" value from the title (e.g., "Twist: 3.06\u00b0" -> 3.06)\n'
        "\n"
        "Return JSON only: "
        '{"pile_number": 2787, "measured_angle": 90.89, "old_twist": 3.06}'
    )

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def read_image(self, image_path: str) -> dict:
        """Returns {"pile_number": int, "measured_angle": float, "old_twist": float}"""

    def parse_response(self, text: str) -> dict:
        """Extract JSON from LLM response text."""
        match = re.search(r"\{[^}]+\}", text)
        if not match:
            raise ValueError(f"No JSON found in response: {text[:200]}")
        data = json.loads(match.group())
        required = {"pile_number", "measured_angle", "old_twist"}
        if not required.issubset(data.keys()):
            raise ValueError(
                f"Missing required fields. Need {required}, got {set(data.keys())}"
            )
        return {
            "pile_number": int(data["pile_number"]),
            "measured_angle": float(data["measured_angle"]),
            "old_twist": float(data["old_twist"]),
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
