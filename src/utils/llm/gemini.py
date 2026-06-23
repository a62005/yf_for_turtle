import json
import logging
import google.generativeai as genai
from .base import BaseLLMProvider

class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model_name: str):
        super().__init__(api_key, model_name)
        genai.configure(api_key=self.api_key)
        self.model_cls = genai.GenerativeModel

    def generate(self, prompt: str, system_instruction: str = None, temperature: float = 0.2) -> str:
        model = self.model_cls(
            model_name=self.model_name,
            system_instruction=system_instruction
        )
        response = model.generate_content(
            prompt,
            generation_config={"temperature": temperature}
        )
        return response.text.strip()

    def generate_json(self, prompt: str, system_instruction: str = None, temperature: float = 0.2) -> dict:
        model = self.model_cls(
            model_name=self.model_name,
            system_instruction=system_instruction
        )
        response = model.generate_content(
            prompt,
            generation_config={
                "response_mime_type": "application/json",
                "temperature": temperature
            }
        )
        return json.loads(response.text.strip())
