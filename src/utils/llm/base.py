from abc import ABC, abstractmethod

class BaseLLMProvider(ABC):
    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name

    @abstractmethod
    def generate(self, prompt: str, system_instruction: str = None, temperature: float = 0.2) -> str:
        """Sends a plain text prompt and returns the response string."""
        pass

    @abstractmethod
    def generate_json(self, prompt: str, system_instruction: str = None, temperature: float = 0.2) -> dict:
        """Sends a prompt and returns a parsed JSON dictionary."""
        pass
