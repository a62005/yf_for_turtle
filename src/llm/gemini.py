import json
import logging
from google import genai
from .base import BaseLLMProvider

class GeminiProvider(BaseLLMProvider):
    FALLBACK_MODELS = [
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",
        "gemini-3.5-flash",
    ]

    def __init__(self, api_key: str, model_name: str):
        # 自動映射過期、無額度或高延遲模型，預設採用高反應速度的 gemini-3.5-flash-lite
        target_model = model_name
        if model_name in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-3.1-flash-lite", "gemini-3.5-flash"]:
            logging.info(f"[LLM] 偵測到模型 {model_name}，自動切換至高速主力模型 gemini-3.5-flash-lite")
            target_model = "gemini-3.5-flash-lite"
            
        super().__init__(api_key, target_model)
        self._client = None

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _generate_with_fallback(self, prompt: str, config: dict):
        client = self._get_client()
        models_to_try = [self.model_name] + [m for m in self.FALLBACK_MODELS if m != self.model_name]
        last_err = None
        for idx, m_name in enumerate(models_to_try):
            try:
                return client.models.generate_content(
                    model=m_name,
                    contents=prompt,
                    config=config
                )
            except Exception as e:
                last_err = e
                err_str = str(e)
                # 若該模型不支援 thinking_config (例如 400 INVALID_ARGUMENT)，移除後重試同模型
                if "thinking_config" in config and ("thinking" in err_str.lower() or "400" in err_str or "INVALID_ARGUMENT" in err_str):
                    fallback_config = {k: v for k, v in config.items() if k != "thinking_config"}
                    try:
                        return client.models.generate_content(
                            model=m_name,
                            contents=prompt,
                            config=fallback_config
                        )
                    except Exception as inner_e:
                        last_err = inner_e
                        err_str = str(inner_e)
                # 若為可重試之伺服器忙碌或模型不可用 (503 / 429 / 404)，自動嘗試備援模型
                if idx < len(models_to_try) - 1 and any(code in err_str for code in ("503", "UNAVAILABLE", "429", "404", "NOT_FOUND")):
                    logging.warning(f"[LLM] 模型 {m_name} 暫時不可用 ({last_err})，自動切換備援模型 {models_to_try[idx + 1]}")
                    continue
                raise last_err
        raise last_err

    def generate(self, prompt: str, system_instruction: str = None, temperature: float = 0.2) -> str:
        config = {
            "temperature": temperature,
            "thinking_config": {"thinking_budget": 0},
        }
        if system_instruction:
            config["system_instruction"] = system_instruction
            
        response = self._generate_with_fallback(prompt, config)
        return response.text.strip()

    def generate_json(self, prompt: str, system_instruction: str = None, temperature: float = 0.2) -> dict:
        config = {
            "temperature": temperature,
            "response_mime_type": "application/json",
            "thinking_config": {"thinking_budget": 0},
        }
        if system_instruction:
            config["system_instruction"] = system_instruction
            
        response = self._generate_with_fallback(prompt, config)
        return json.loads(response.text.strip())

    def generate_json_with_search(self, prompt: str, system_instruction: str = None) -> dict:
        """啟用 Google 搜尋 Grounding 來動態擷取最新的網路資訊，並返回 JSON 格式。"""
        config = {
            "temperature": 0.0,
            "response_mime_type": "application/json",
            "tools": [{"google_search": {}}]
        }
        if system_instruction:
            config["system_instruction"] = system_instruction
            
        response = self._generate_with_fallback(prompt, config)
        return json.loads(response.text.strip())
