import pytest
from unittest.mock import MagicMock, patch
from src.utils.llm import LLMProviderFactory, GeminiProvider, AgnesProvider

def test_factory_missing_env():
    with patch.dict('os.environ', {}, clear=True):
        with pytest.raises(ValueError) as excinfo:
            LLMProviderFactory.get_provider()
        assert "LLM API key" in str(excinfo.value)

def test_factory_missing_model():
    with patch.dict('os.environ', {'LLM_API_KEY': 'some_key'}, clear=True):
        with pytest.raises(ValueError) as excinfo:
            LLMProviderFactory.get_provider()
        assert "LLM Model" in str(excinfo.value)

def test_factory_resolves_gemini():
    with patch.dict('os.environ', {'LLM_API_KEY': 'k', 'LLM_MODEL': 'gemini-2.5-flash'}, clear=True):
        provider = LLMProviderFactory.get_provider()
        assert isinstance(provider, GeminiProvider)
        assert provider.api_key == "k"
        assert provider.model_name == "gemini-2.5-flash"

def test_factory_resolves_agnes():
    with patch.dict('os.environ', {'LLM_API_KEY': 'k', 'LLM_MODEL': 'agnes-2.0-flash'}, clear=True):
        provider = LLMProviderFactory.get_provider()
        assert isinstance(provider, AgnesProvider)
        assert provider.api_key == "k"
        assert provider.model_name == "agnes-2.0-flash"
