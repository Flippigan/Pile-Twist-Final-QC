# providers/openai_provider.py
import base64
from pathlib import Path

from openai import OpenAI

from . import VisionProvider, register_provider


@register_provider("openai")
class OpenAIProvider(VisionProvider):
    def __init__(self, config: dict):
        super().__init__(config)
        kwargs = {}
        if config.get("openai_api_key"):
            kwargs["api_key"] = config["openai_api_key"]
        self.client = OpenAI(**kwargs)

    def read_image(self, image_path: str) -> dict:
        image_data = base64.b64encode(Path(image_path).read_bytes()).decode()
        suffix = Path(image_path).suffix.lower()
        mime = "image/png" if suffix == ".png" else "image/jpeg"

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{image_data}"},
                        },
                    ],
                }
            ],
            max_tokens=200,
        )
        return self.parse_response(response.choices[0].message.content)
