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
            '{"pile_number": 2787, "measured_angle": 90.89, "old_twist": 3.06}'
        )
        assert result == {
            "pile_number": 2787,
            "measured_angle": 90.89,
            "old_twist": 3.06,
        }

    def test_json_embedded_in_text(self):
        p = self._make_provider()
        result = p.parse_response(
            'Here is the data: {"pile_number": 777, "measured_angle": 87.35, "old_twist": 4.69} done.'
        )
        assert result["pile_number"] == 777
        assert result["measured_angle"] == 87.35

    def test_no_json_raises(self):
        p = self._make_provider()
        with pytest.raises(ValueError, match="No JSON found"):
            p.parse_response("I cannot read this image")

    def test_missing_fields_raises(self):
        p = self._make_provider()
        with pytest.raises(ValueError, match="Missing required fields"):
            p.parse_response('{"pile_number": 2787}')

    def test_types_coerced(self):
        p = self._make_provider()
        result = p.parse_response(
            '{"pile_number": "2787", "measured_angle": "90.89", "old_twist": "3.06"}'
        )
        assert isinstance(result["pile_number"], int)
        assert isinstance(result["measured_angle"], float)
        assert isinstance(result["old_twist"], float)


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
