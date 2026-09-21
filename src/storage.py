# src/storage.py
import os
from datetime import datetime
from abc import ABC, abstractmethod
from src.utils.audit_logger import save_json_file, delete_data_file

class BaseStorage(ABC):
    @abstractmethod
    def save(self, data: dict, identifier: str, sub_dir: str = "", overwrite: bool = False) -> str:
        pass

    @abstractmethod
    def delete(self, identifier: str, sub_dir: str = "") -> bool:
        pass

class JsonStorage(BaseStorage):
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)

    def save(self, data: dict, identifier: str, sub_dir: str = "", overwrite: bool = False) -> str:
        target_dir = os.path.join(self.data_dir, sub_dir)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        if overwrite:
            filename = f"{identifier}.json" if not identifier.endswith(".json") else identifier
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"{timestamp}_{identifier}.json"
            
        filepath = os.path.join(target_dir, filename)
        return save_json_file(filepath, data)

    def delete(self, identifier: str, sub_dir: str = "") -> bool:
        target_dir = os.path.join(self.data_dir, sub_dir)
        filename = f"{identifier}.json" if not identifier.endswith(".json") else identifier
        filepath = os.path.join(target_dir, filename)
        return delete_data_file(filepath)
