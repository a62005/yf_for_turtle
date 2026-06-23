import json
import logging
from google import genai
from .base import BaseLLMProvider

class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model_name: str):
        # 自動映射過期或無額度的模型
        target_model = model_name
        if model_name in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]:
            logging.info(f"[LLM] 偵測到可能已過期或免費配額為 0 的模型 {model_name}，自動切換至最新可用模型 gemini-3.5-flash")
            target_model = "gemini-3.5-flash"
            
        super().__init__(api_key, target_model)

    def _get_client(self) -> genai.Client:
        return genai.Client(api_key=self.api_key)

    def generate(self, prompt: str, system_instruction: str = None, temperature: float = 0.2) -> str:
        config = {
            "temperature": temperature,
        }
        if system_instruction:
            config["system_instruction"] = system_instruction
            
        client = self._get_client()
        response = client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config
        )
        return response.text.strip()

    def generate_json(self, prompt: str, system_instruction: str = None, temperature: float = 0.2) -> dict:
        config = {
            "temperature": temperature,
            "response_mime_type": "application/json"
        }
        if system_instruction:
            config["system_instruction"] = system_instruction
            
        client = self._get_client()
        response = client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config
        )
        return json.loads(response.text.strip())
