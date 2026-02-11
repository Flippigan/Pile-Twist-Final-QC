# tests/test_providers.py
import pytest
from providers import VisionProvider, register_provider, get_provider, PROVIDERS


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
