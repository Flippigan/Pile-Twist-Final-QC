# providers/claude_provider.py
import base64
from pathlib import Path

import anthropic

from . import VisionProvider, register_provider


@register_provider("claude")
class ClaudeProvider(VisionProvider):
    def __init__(self, config: dict):
        super().__init__(config)
        kwargs = {}
        if config.get("claude_api_key"):
            kwargs["api_key"] = config["claude_api_key"]
        self.client = anthropic.Anthropic(**kwargs)

    def read_image(self, image_path: str) -> dict:
        image_data = base64.b64encode(Path(image_path).read_bytes()).decode()
        suffix = Path(image_path).suffix.lower()
        mime = "image/png" if suffix == ".png" else "image/jpeg"

        response = self.client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=200,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime,
                                "data": image_data,
                            },
                        },
                        {"type": "text", "text": self.PROMPT},
                    ],
                }
            ],
        )
        return self.parse_response(response.content[0].text)
