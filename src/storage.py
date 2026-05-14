# src/storage.py
import os
import json
from datetime import datetime
from abc import ABC, abstractmethod

class BaseStorage(ABC):
    @abstractmethod
    def save(self, data: dict, identifier: str) -> str:
        pass

class JsonStorage(BaseStorage):
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def save(self, data: dict, identifier: str) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{timestamp}_{identifier}.json"
        filepath = os.path.join(self.data_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
        return filepath
