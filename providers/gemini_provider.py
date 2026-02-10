# providers/gemini_provider.py
import base64
from pathlib import Path

from google import genai

from . import VisionProvider, register_provider


@register_provider("gemini")
class GeminiProvider(VisionProvider):
    def __init__(self, config: dict):
        super().__init__(config)
        self.client = genai.Client(api_key=config.get("gemini_api_key"))

    def read_image(self, image_path: str) -> dict:
        image_data = base64.b64encode(Path(image_path).read_bytes()).decode()
        suffix = Path(image_path).suffix.lower()
        mime = "image/png" if suffix == ".png" else "image/jpeg"

        response = self.client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                {"inline_data": {"mime_type": mime, "data": image_data}},
                self.PROMPT,
            ],
        )
        return self.parse_response(response.text)
