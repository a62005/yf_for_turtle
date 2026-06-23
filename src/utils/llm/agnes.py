import json
import requests
from .base import BaseLLMProvider

class AgnesProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model_name: str):
        super().__init__(api_key, model_name)
        self.agnes_model = self.model_name
        if self.agnes_model.lower() == "agnes":
            self.agnes_model = "agnes-2.0-flash"
        self.api_url = "https://apihub.agnes-ai.com/v1/chat/completions"

    def _call_api(self, prompt: str, system_instruction: str = None, temperature: float = 0.2, response_format: dict = None) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.agnes_model,
            "messages": messages,
            "temperature": temperature
        }
        if response_format:
            payload["response_format"] = response_format

        res = requests.post(self.api_url, json=payload, headers=headers, timeout=15)
        res.raise_for_status()
        res_json = res.json()
        return res_json["choices"][0]["message"]["content"].strip()

    def generate(self, prompt: str, system_instruction: str = None, temperature: float = 0.2) -> str:
        return self._call_api(prompt, system_instruction, temperature)

    def generate_json(self, prompt: str, system_instruction: str = None, temperature: float = 0.2) -> dict:
        content = self._call_api(prompt, system_instruction, temperature, response_format={"type": "json_object"})
        return json.loads(content)
