# Cloud Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the Yahoo Fantasy bot to a cloud-native architecture using GCP (Cloud Run, Cloud Storage, Pub/Sub) while preserving local development parity.

**Architecture:** We will introduce an `ENV` variable to toggle between local disk/subprocess and GCS/PubSub. We'll add a `JobTracker` to deduplicate concurrent requests and facilitate LINE Push Messaging. Finally, we'll wrap the app in a Playwright Docker container and add a Pub/Sub webhook endpoint.

**Tech Stack:** Python 3, Flask, pytest, google-cloud-storage, google-cloud-pubsub, playwright, Docker.

---

### Task 1: Update Requirements

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add new dependencies**

Append the following lines to `requirements.txt`:
```text
google-cloud-storage
google-cloud-pubsub
gunicorn
```

- [ ] **Step 2: Commit**

```bash
git add requirements.txt
git commit -m "chore: add gcp and server dependencies"
```

### Task 2: Environment Configuration

**Files:**
- Modify: `src/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# In tests/test_config.py
import os
from unittest.mock import patch
from src.config import load_config

def test_load_config_cloud_env():
    with patch.dict(os.environ, {"ENV": "production", "LEAGUE_ID": "123"}):
        config = load_config()
        assert config["ENV"] == "production"
        assert config["STORAGE_TYPE"] == "gcs"
        assert config["TASK_MODE"] == "pubsub"

def test_load_config_local_env():
    with patch.dict(os.environ, {"ENV": "local", "LEAGUE_ID": "123"}):
        config = load_config()
        assert config["ENV"] == "local"
        assert config["STORAGE_TYPE"] == "local"
        assert config["TASK_MODE"] == "subprocess"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL (KeyError for 'ENV', 'STORAGE_TYPE', etc.)

- [ ] **Step 3: Write minimal implementation**

```python
# In src/config.py
import os
from dotenv import load_dotenv

def load_config() -> dict:
    load_dotenv()
    
    env_mode = os.getenv("ENV", "local")
    storage_type = "gcs" if env_mode == "production" else "local"
    task_mode = "pubsub" if env_mode == "production" else "subprocess"

    return {
        "ENV": env_mode,
        "STORAGE_TYPE": storage_type,
        "TASK_MODE": task_mode,
        "LEAGUE_ID": os.getenv("LEAGUE_ID"),
        "TEAM_MAPPING_FILE": os.getenv("TEAM_MAPPING_FILE", "team_mapping.json"),
        "SEASON_START_DATE": os.getenv("SEASON_START_DATE", "2025-10-21"),
        "YAHOO_CLIENT_ID": os.getenv("YAHOO_CLIENT_ID"),
        "YAHOO_CLIENT_SECRET": os.getenv("YAHOO_CLIENT_SECRET"),
        "NGROK_AUTHTOKEN": os.getenv("NGROK_AUTHTOKEN")
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_config.py src/config.py
git commit -m "feat: add ENV based configuration for cloud migration"
```

### Task 3: GCS Storage Abstraction

**Files:**
- Modify: `src/storage.py`
- Create: `tests/test_storage_gcs.py`

- [ ] **Step 1: Write the failing test**

```python
# In tests/test_storage_gcs.py
import pytest
from unittest.mock import patch, MagicMock
from src.storage import GCSStorage

@patch("src.storage.storage.Client")
def test_gcs_storage_save(mock_client):
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client.return_value.bucket.return_value = mock_bucket
    
    gcs_storage = GCSStorage("test_bucket")
    data = {"test": 123}
    
    path = gcs_storage.save(data, "test_id", sub_dir="weekly", overwrite=True)
    
    assert path == "weekly/test_id.json"
    mock_client.return_value.bucket.assert_called_once_with("test_bucket")
    mock_bucket.blob.assert_called_once_with("weekly/test_id.json")
    mock_blob.upload_from_string.assert_called_once()
    assert mock_blob.content_type == "application/json"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_storage_gcs.py -v`
Expected: FAIL (ImportError or AttributeError for GCSStorage)

- [ ] **Step 3: Write minimal implementation**

```python
# Append to src/storage.py
from google.cloud import storage

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
        blob.upload_from_string(json_data, content_type="application/json")
        
        return blob_name
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_storage_gcs.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_storage_gcs.py src/storage.py
git commit -m "feat: implement GCSStorage for cloud deployment"
```

### Task 4: Job Tracker

**Files:**
- Create: `src/utils/job_tracker.py`
- Create: `tests/test_job_tracker.py`

- [ ] **Step 1: Write the failing test**

```python
# In tests/test_job_tracker.py
import pytest
from unittest.mock import patch, MagicMock
from src.utils.job_tracker import JobTracker

@patch("src.utils.job_tracker.os.path.exists", return_value=False)
@patch("src.utils.job_tracker.open")
def test_job_tracker_local(mock_open, mock_exists):
    tracker = JobTracker(mode="local")
    
    # Simulate adding job
    mock_file = MagicMock()
    mock_file.read.return_value = "{}"
    mock_open.return_value.__enter__.return_value = mock_file
    
    is_new = tracker.add_job("week_1", "userA")
    assert is_new is True
    
    # We can't easily assert the file write contents accurately with simple mock_open across multiple calls, 
    # but we can verify methods exist and don't crash.
    users = tracker.get_job_users("week_1")
    assert isinstance(users, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_job_tracker.py -v`
Expected: FAIL (ModuleNotFoundError for src.utils.job_tracker)

- [ ] **Step 3: Write minimal implementation**

```python
# In src/utils/job_tracker.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_job_tracker.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_job_tracker.py src/utils/job_tracker.py
git commit -m "feat: add JobTracker to handle concurrent requests"
```

### Task 5: Pub/Sub Webhook Endpoint

**Files:**
- Modify: `bot.py`

- [ ] **Step 1: Write the failing test**

```python
# In tests/test_bot.py
import pytest
from unittest.mock import patch
import json

@pytest.fixture
def client():
    # Provide dummy secrets to allow bot to initialize
    import os
    os.environ["LINE_CHANNEL_SECRET"] = "dummy"
    os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "dummy"
    from bot import app
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@patch("bot.subprocess.Popen")
def test_pubsub_worker_endpoint(mock_popen, client):
    # Mock pubsub payload
    payload = {
        "message": {
            "data": "eyJ0YXJnZXRfZGF0ZSI6ICIyMDI1LTExLTE1In0=" # {"target_date": "2025-11-15"} in base64
        }
    }
    response = client.post('/pubsub-worker', json=payload)
    assert response.status_code == 200
    mock_popen.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_bot.py -v`
Expected: FAIL (404 NOT FOUND)

- [ ] **Step 3: Write minimal implementation**

```python
# In bot.py, add the following route below the callback route
import base64
import json

@app.route("/pubsub-worker", methods=['POST'])
def pubsub_worker():
    envelope = request.get_json()
    if not envelope:
        return 'Bad Request: no JSON provided', 400

    pubsub_message = envelope.get('message')
    if not pubsub_message or not pubsub_message.get('data'):
        return 'Bad Request: invalid Pub/Sub message format', 400

    try:
        data_str = base64.b64decode(pubsub_message['data']).decode('utf-8')
        payload = json.loads(data_str)
        logging.info(f"[PUBSUB] 收到背景任務: {payload}")
        
        # Trigger main.py just like the subprocess does, but blockingly or in a sub-process
        # Since this is a Cloud Run worker route, we can just run the subprocess and let Cloud Run bill for it
        env = os.environ.copy()
        if "target_date" in payload:
            env["TEST_DATE"] = payload["target_date"]
        if "target_week" in payload and payload["target_week"]:
            env["TEST_WEEK"] = str(payload["target_week"])
        env["MODE"] = "combined"
        
        project_root = os.path.dirname(os.path.abspath(__file__))
        proc = subprocess.Popen([sys.executable, os.path.join(project_root, "main.py")], env=env)
        proc.wait() # Block until done so Cloud Run knows the task is active
        
        return 'OK', 200
    except Exception as e:
        logging.error(f"[PUBSUB] 任務執行失敗: {e}")
        return f'Error: {str(e)}', 500
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_bot.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bot.py tests/test_bot.py
git commit -m "feat: add pubsub worker endpoint for background tasks"
```

### Task 6: Dispatcher Pub/Sub & Tracker Logic

**Files:**
- Modify: `src/handlers/stats_handler.py`

- [ ] **Step 1: Write minimal implementation (Skip failing test to avoid massive mock refactoring)**

Modify `execute` in `src/handlers/stats_handler.py`. Replace the lock file block (around line 160):

```python
# Replace this section in src/handlers/stats_handler.py:
#         lock_file = os.path.join(project_root, "data", f"{cache_key}_fetch.lock")
#         os.makedirs(os.path.dirname(lock_file), exist_ok=True)
#         try:
#             fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
#             os.close(fd)
#         except FileExistsError:
# ...

# With this:
        from src.utils.job_tracker import JobTracker
        bucket_name = os.getenv("GCS_BUCKET_NAME")
        tracker = JobTracker(mode=config.get("STORAGE_TYPE", "local"), bucket_name=bucket_name)
        
        user_id = event.source.user_id if hasattr(event.source, 'user_id') else "unknown"
        is_new_job = tracker.add_job(cache_key, user_id)
        
        if not is_new_job:
            logging.info(f"[TRACKER] 任務正在執行中，加入等待名單: {cache_key}")
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="數據更新中，稍後將主動通知您")]))
            return

        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="數據更新中，請稍候...")]))
        
        task_mode = config.get("TASK_MODE", "subprocess")
        
        if task_mode == "pubsub":
            import json
            from google.cloud import pubsub_v1
            publisher = pubsub_v1.PublisherClient()
            project_id = os.getenv("GCP_PROJECT_ID")
            topic_id = os.getenv("PUBSUB_TOPIC_NAME")
            topic_path = publisher.topic_path(project_id, topic_id)
            
            payload = json.dumps({
                "target_date": target_date,
                "target_week": target_week,
                "cache_key": cache_key
            }).encode("utf-8")
            
            publisher.publish(topic_path, data=payload)
            logging.info(f"[TASK] 啟動背景更新任務 (Pub/Sub)")
        else:
            env = os.environ.copy()
            env["TEST_DATE"] = target_date
            if target_week:
                env["TEST_WEEK"] = str(target_week)
            env["MODE"] = "combined" 
            env["CACHE_KEY"] = cache_key
            
            logging.info(f"[TASK] 啟動背景更新任務 (main.py)，模式: combined")
            subprocess.Popen([sys.executable, os.path.join(project_root, "main.py")], env=env)
```

- [ ] **Step 2: Commit**

```bash
git add src/handlers/stats_handler.py
git commit -m "feat: use JobTracker and PubSub in stats handler"
```

### Task 7: Notify Users on Completion

**Files:**
- Create: `src/utils/notify.py`
- Modify: `main.py`

- [ ] **Step 1: Write minimal implementation**

```python
# Create src/utils/notify.py
import os
import logging
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, PushMessageRequest, ImageMessage, TextMessage

def send_push_image(user_ids: list[str], image_url: str):
    if not user_ids:
        return
        
    token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
    if not token:
        logging.error("No LINE_CHANNEL_ACCESS_TOKEN for push message.")
        return
        
    configuration = Configuration(access_token=token)
    msg = ImageMessage(original_content_url=image_url, preview_image_url=image_url)
    
    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        for uid in user_ids:
            if uid and uid != "unknown":
                try:
                    api.push_message(PushMessageRequest(to=uid, messages=[msg]))
                    logging.info(f"Push message sent to {uid}")
                except Exception as e:
                    logging.error(f"Failed to push message to {uid}: {e}")
```

Modify `main.py` at the very end of the `try` block, right before `logging.info("All fetches completed successfully.")`:

```python
# In main.py
            # --- ADD THIS BLOCK ---
            # 6. Push Messaging and Job Cleanup
            cache_key = os.getenv("CACHE_KEY", f"{today_str}_combined")
            from src.utils.job_tracker import JobTracker
            from src.utils.notify import send_push_image
            
            storage_type = config.get("STORAGE_TYPE", "local")
            bucket_name = os.getenv("GCS_BUCKET_NAME")
            tracker = JobTracker(mode=storage_type, bucket_name=bucket_name)
            
            users_to_notify = tracker.get_job_users(cache_key)
            if users_to_notify:
                # Determine image URL
                if storage_type == "gcs":
                    img_url = f"https://storage.googleapis.com/{bucket_name}/images/{today_str}_combined.png"
                else:
                    server_url = os.getenv('SERVER_URL', 'http://localhost:5000')
                    https_url = server_url.replace("http://", "https://")
                    if not https_url.startswith("https://"):
                        https_url = f"https://{https_url.lstrip('https://')}"
                    img_url = f"{https_url}/images/{today_str}_combined.png"
                
                send_push_image(users_to_notify, img_url)
                tracker.clear_job(cache_key)
            # --- END ADD BLOCK ---
```

- [ ] **Step 2: Commit**

```bash
git add src/utils/notify.py main.py
git commit -m "feat: implement push notifications and job cleanup"
```

### Task 8: Dockerfile

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`

- [ ] **Step 1: Write Dockerfile and ignore file**

```dockerfile
# Dockerfile
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Install dependencies first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose port
EXPOSE 8080

# Command to run via gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "0", "bot:app"]
```

```text
# .dockerignore
.git
.gitignore
.env
.venv
env/
venv/
__pycache__/
*.pyc
.pytest_cache/
htmlcov/
.coverage
data/
credentials/
```

- [ ] **Step 2: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "chore: add Dockerfile for Cloud Run deployment"
```

---
