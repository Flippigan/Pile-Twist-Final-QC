# tests/test_providers.py
import pytest
from providers import VisionProvider, register_provider, get_provider, PROVIDERS


class TestParseResponse:
    """Test the shared JSON parsing logic in VisionProvider."""

    def _make_provider(self):
        """Create a concrete subclass for testing the base class methods."""
        class FakeProvider(VisionProvider):
            def read_image(self, image_path):
                return {}
        return FakeProvider({})

    def test_valid_json(self):
        p = self._make_provider()
        result = p.parse_response(
            '{"measured_angle": 90.89}'
        )
        assert result == {"measured_angle": 90.89}

    def test_json_embedded_in_text(self):
        p = self._make_provider()
        result = p.parse_response(
            'Here is the data: {"measured_angle": 87.35} done.'
        )
        assert result["measured_angle"] == 87.35

    def test_no_json_raises(self):
        p = self._make_provider()
        with pytest.raises(ValueError, match="No JSON found"):
            p.parse_response("I cannot read this image")

    def test_missing_fields_raises(self):
        p = self._make_provider()
        with pytest.raises(ValueError, match="Missing required field"):
            p.parse_response('{"pile_number": 27870}')

    def test_type_coerced(self):
        p = self._make_provider()
        result = p.parse_response(
            '{"measured_angle": "90.89"}'
        )
        assert isinstance(result["measured_angle"], float)

    def test_extra_fields_ignored(self):
        """LLM may return extra fields — they should be ignored."""
        p = self._make_provider()
        result = p.parse_response(
            '{"measured_angle": 90.89, "pile_number": 27870}'
        )
        assert result == {"measured_angle": 90.89}


class TestRegistry:
    def test_register_and_get(self):
        @register_provider("fake_test")
        class FakeTestProvider(VisionProvider):
            def __init__(self, config):
                pass
            def read_image(self, image_path):
                return {}

        provider = get_provider("fake_test", {})
        assert isinstance(provider, FakeTestProvider)

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("nonexistent_provider_xyz", {})


from unittest.mock import patch, MagicMock


class TestOpenAIProvider:
    def test_read_image_calls_api(self, sample_image):
        from providers.openai_provider import OpenAIProvider

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            '{"measured_angle": 90.89}'
        )

        with patch("providers.openai_provider.OpenAI") as MockClient:
            MockClient.return_value.chat.completions.create.return_value = mock_response
            provider = OpenAIProvider({"openai_api_key": "test-key"})
            result = provider.read_image(str(sample_image))

        assert result["measured_angle"] == 90.89


class TestClaudeProvider:
    def test_read_image_calls_api(self, sample_image):
        from providers.claude_provider import ClaudeProvider

        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = (
            '{"measured_angle": 87.35}'
        )

        with patch("providers.claude_provider.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_response
            provider = ClaudeProvider({"claude_api_key": "test-key"})
            result = provider.read_image(str(sample_image))

        assert result["measured_angle"] == 87.35


class TestGeminiProvider:
    def test_read_image_calls_api(self, sample_image):
        from providers.gemini_provider import GeminiProvider

        mock_response = MagicMock()
        mock_response.text = (
            '{"measured_angle": 92.35}'
        )

        with patch("providers.gemini_provider.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_response
            provider = GeminiProvider({"gemini_api_key": "test-key"})
            result = provider.read_image(str(sample_image))

        assert result["measured_angle"] == 92.35
