import os
import json
from filelock import FileLock

LOCAL_TRACKER_FILE = os.path.join("data", "pending_jobs.json")
LOCK_FILE = LOCAL_TRACKER_FILE + ".lock"

class JobTracker:
    def __init__(self, mode="local", bucket_name=None):
        self.mode = mode
        self.bucket_name = bucket_name
        self.blob_name = "pending_jobs.json"
        
        if self.mode == "gcs" and self.bucket_name:
            from google.cloud import storage
            self.client = storage.Client()
            self.bucket = self.client.bucket(self.bucket_name)

    def _read_data(self) -> dict:
        if self.mode == "local":
            if not os.path.exists(LOCAL_TRACKER_FILE):
                return {}
            try:
                with open(LOCAL_TRACKER_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        else:
            blob = self.bucket.blob(self.blob_name)
            if not blob.exists():
                return {}
            try:
                return json.loads(blob.download_as_string())
            except Exception:
                return {}

    def _write_data(self, data: dict):
        if self.mode == "local":
            os.makedirs(os.path.dirname(LOCAL_TRACKER_FILE), exist_ok=True)
            with open(LOCAL_TRACKER_FILE, "w") as f:
                json.dump(data, f)
        else:
            blob = self.bucket.blob(self.blob_name)
            blob.upload_from_string(json.dumps(data), content_type="application/json")

    def add_job(self, task_id: str, user_id: str) -> bool:
        """Adds a user to a task. Returns True if task is new, False if already exists."""
        if self.mode == "local":
            os.makedirs(os.path.dirname(LOCAL_TRACKER_FILE), exist_ok=True)
            with FileLock(LOCK_FILE):
                data = self._read_data()
                is_new = task_id not in data
                if is_new:
                    data[task_id] = []
                if user_id and user_id not in data[task_id]:
                    data[task_id].append(user_id)
                self._write_data(data)
                return is_new
        else:
            # GCS doesn't support fine-grained locking easily, using simple read-modify-write 
            # for low traffic
            data = self._read_data()
            is_new = task_id not in data
            if is_new:
                data[task_id] = []
            if user_id and user_id not in data[task_id]:
                data[task_id].append(user_id)
            self._write_data(data)
            return is_new

    def get_job_users(self, task_id: str) -> list[str]:
        data = self._read_data()
        return data.get(task_id, [])

    def clear_job(self, task_id: str):
        if self.mode == "local":
            with FileLock(LOCK_FILE):
                data = self._read_data()
                if task_id in data:
                    del data[task_id]
                    self._write_data(data)
        else:
            data = self._read_data()
            if task_id in data:
                del data[task_id]
                self._write_data(data)
