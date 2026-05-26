# src/storage.py
import os
import json
from datetime import datetime
from abc import ABC, abstractmethod
from google.cloud import storage

class BaseStorage(ABC):
    @abstractmethod
    def save(self, data: dict, identifier: str, sub_dir: str = "", overwrite: bool = False) -> str:
        pass

class JsonStorage(BaseStorage):
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def save(self, data: dict, identifier: str, sub_dir: str = "", overwrite: bool = False) -> str:
        target_dir = os.path.join(self.data_dir, sub_dir)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        if overwrite:
            filename = f"{identifier}.json"
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"{timestamp}_{identifier}.json"
            
        filepath = os.path.join(target_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
        return filepath

class GCSStorage(BaseStorage):
    def __init__(self, bucket_name: str):
        self.bucket_name = bucket_name
        self.client = storage.Client()

    def save(self, data: dict, identifier: str, sub_dir: str = "", overwrite: bool = False) -> str:
        if overwrite:
            filename = f"{identifier}.json"
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"{timestamp}_{identifier}.json"
            
        blob_name = os.path.join(sub_dir, filename).replace("\\", "/") # Ensure GCS path format
        if blob_name.startswith("/"):
            blob_name = blob_name[1:]
            
        bucket = self.client.bucket(self.bucket_name)
        blob = bucket.blob(blob_name)
        
        json_data = json.dumps(data, indent=4, ensure_ascii=False)
        blob.content_type = "application/json"
        blob.upload_from_string(json_data, content_type="application/json")
        
        return blob_name
