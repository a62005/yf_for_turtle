import os
from .base import BaseLLMProvider

class LLMProviderFactory:
    @staticmethod
    def get_provider(api_key: str = None, model_name: str = None) -> BaseLLMProvider:
        key = api_key or os.getenv("LLM_API_KEY")
        model = model_name or os.getenv("LLM_MODEL")

        if not key:
            raise ValueError("LLM API key (LLM_API_KEY) is not configured in the environment.")
        if not model:
            raise ValueError("LLM Model (LLM_MODEL) is not configured in the environment.")

        model_lower = model.lower()
        if "agnes" in model_lower:
            from .agnes import AgnesProvider
            return AgnesProvider(api_key=key, model_name=model)
        else:
            from .gemini import GeminiProvider
            return GeminiProvider(api_key=key, model_name=model)
