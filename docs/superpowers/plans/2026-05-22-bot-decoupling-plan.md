# Bot Handler Decoupling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decouple `bot.py`'s message routing and business logic by implementing a Command Dispatcher and dedicated Domain Handlers (e.g., StatsHandler).

**Architecture:** A 3-tier architecture. `bot.py` checks for the `#` prefix. `CommandDispatcher` routes the message to the appropriate handler. `BaseHandler` provides an interface. `StatsHandler` inherits from `BaseHandler` and handles specific fantasy stats logic.

**Tech Stack:** Python, Flask, line-bot-sdk, pytest.

---

### Task 1: Create Base Handler Interface

**Files:**
- Create: `src/handlers/__init__.py`
- Create: `src/handlers/base_handler.py`

- [ ] **Step 1: Write the interface definition**

```python
# src/handlers/base_handler.py
from abc import ABC, abstractmethod
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration

class BaseHandler(ABC):
    """Base interface for all bot message handlers."""
    
    @abstractmethod
    def can_handle(self, user_text: str) -> bool:
        """Return True if this handler can process the given text."""
        pass
        
    @abstractmethod
    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        """Execute the core logic and handle LINE API replies."""
        pass
```

- [ ] **Step 2: Create package init**

```python
# src/handlers/__init__.py
# Empty file to make handlers a package
```

- [ ] **Step 3: Commit**

```bash
git add src/handlers/base_handler.py src/handlers/__init__.py
git commit -m "feat(handlers): add BaseHandler interface"
```

---

### Task 2: Implement Command Dispatcher

**Files:**
- Create: `src/handlers/dispatcher.py`
- Create: `tests/handlers/test_dispatcher.py`

- [ ] **Step 1: Write failing test for Dispatcher**

```python
# tests/handlers/test_dispatcher.py
import pytest
from unittest.mock import Mock, patch
from src.handlers.dispatcher import CommandDispatcher
from src.handlers.base_handler import BaseHandler

class MockHandler(BaseHandler):
    def __init__(self, can_handle_result=True):
        self._can_handle_result = can_handle_result
        self.executed = False
        
    def can_handle(self, user_text):
        return self._can_handle_result
        
    def execute(self, event, configuration):
        self.executed = True

def test_dispatcher_routes_to_first_capable_handler():
    dispatcher = CommandDispatcher()
    handler1 = MockHandler(False)
    handler2 = MockHandler(True)
    dispatcher.register(handler1)
    dispatcher.register(handler2)
    
    mock_event = Mock()
    mock_event.message.text = "#test"
    mock_config = Mock()
    
    dispatcher.handle(mock_event, mock_config)
    
    assert not handler1.executed
    assert handler2.executed

def test_dispatcher_ignores_if_no_handler():
    dispatcher = CommandDispatcher()
    handler1 = MockHandler(False)
    dispatcher.register(handler1)
    
    mock_event = Mock()
    mock_event.message.text = "#unknown"
    
    # Should not raise exception
    dispatcher.handle(mock_event, Mock())
    assert not handler1.executed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/handlers/test_dispatcher.py -v`
Expected: FAIL (ModuleNotFoundError or ImportError)

- [ ] **Step 3: Implement CommandDispatcher**

```python
# src/handlers/dispatcher.py
import logging
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from typing import List
from .base_handler import BaseHandler

class CommandDispatcher:
    def __init__(self):
        self._handlers: List[BaseHandler] = []
        
    def register(self, handler: BaseHandler) -> None:
        """Register a handler to the dispatcher."""
        self._handlers.append(handler)
        
    def handle(self, event: MessageEvent, configuration: Configuration) -> None:
        """Route the event to the appropriate handler."""
        user_text = event.message.text.strip()
        
        for handler in self._handlers:
            try:
                if handler.can_handle(user_text):
                    handler.execute(event, configuration)
                    return # Stop routing once a handler takes it
            except Exception as e:
                logging.error(f"[Dispatcher] Handler {handler.__class__.__name__} failed: {e}")
                
        logging.info(f"[Dispatcher] No handler found for command: {user_text}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/handlers/test_dispatcher.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/handlers/dispatcher.py tests/handlers/test_dispatcher.py
git commit -m "feat(handlers): implement CommandDispatcher"
```

---

### Task 3: Implement StatsHandler Skeleton & `can_handle`

**Files:**
- Create: `src/handlers/stats_handler.py`
- Create: `tests/handlers/test_stats_handler.py`

- [ ] **Step 1: Write failing test for regex logic**

```python
# tests/handlers/test_stats_handler.py
import pytest
from src.handlers.stats_handler import StatsHandler

def test_stats_handler_can_handle():
    handler = StatsHandler()
    assert handler.can_handle("#戰績") is True
    assert handler.can_handle("#當天戰績") is True
    assert handler.can_handle("#當週戰績") is True
    assert handler.can_handle("#戰績W23") is True
    assert handler.can_handle("#戰績w23") is True
    assert handler.can_handle("#戰績20250101") is True
    
    assert handler.can_handle("#獎金") is False
    assert handler.can_handle("戰績") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/handlers/test_stats_handler.py -v`
Expected: FAIL

- [ ] **Step 3: Implement regex logic in StatsHandler**

```python
# src/handlers/stats_handler.py
import re
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from .base_handler import BaseHandler

class StatsHandler(BaseHandler):
    def __init__(self):
        self.combined_pattern = re.compile(r"^#戰績$")
        self.daily_pattern = re.compile(r"^#當天戰績$")
        self.weekly_pattern = re.compile(r"^#當週戰績$")
        self.specific_week_pattern = re.compile(r"^#戰績W(\d+)$", re.IGNORECASE)
        self.specific_date_pattern = re.compile(r"^#戰績(\d{8})$")

    def parse_command(self, user_text: str) -> tuple[str | None, str | int | None]:
        if self.combined_pattern.match(user_text):
            return "combined", None
        elif self.daily_pattern.match(user_text):
            return "daily", None
        elif self.weekly_pattern.match(user_text):
            return "weekly", None
        
        m_week = self.specific_week_pattern.match(user_text)
        if m_week:
            return "specific_week", int(m_week.group(1))
            
        m_date = self.specific_date_pattern.match(user_text)
        if m_date:
            raw_date = m_date.group(1)
            return "specific_date", f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
            
        return None, None

    def can_handle(self, user_text: str) -> bool:
        cmd_type, _ = self.parse_command(user_text)
        return cmd_type is not None

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        pass # To be implemented in next task
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/handlers/test_stats_handler.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/handlers/stats_handler.py tests/handlers/test_stats_handler.py
git commit -m "feat(handlers): implement StatsHandler can_handle logic"
```

---

### Task 4: Migrate `execute` Logic to StatsHandler

**Files:**
- Modify: `src/handlers/stats_handler.py`

- [ ] **Step 1: Write test for missing imports and logic flow (Basic Sanity)**
Since full execution involves complex dependencies (`os`, `sys`, `subprocess`, `ApiClient`, etc.), we'll ensure the execute method parses commands without crashing. Mocking the entire `bot.py` flow deeply here is complex for a simple refactor, but we must verify the code compiles and imports successfully.

- [ ] **Step 2: Migrate execution logic**
Replace the empty `execute` method in `src/handlers/stats_handler.py` with the logic from `bot.py`. We need to add the required imports at the top of the file.

```python
# src/handlers/stats_handler.py
import re
import os
import sys
import psutil
import logging
import subprocess
from datetime import datetime
import pytz
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, ImageMessage
from .base_handler import BaseHandler

# Required project imports
from src.config import load_config
from src.cache_utils import load_league_metadata, is_empty_data
from src.utils.time_utils import get_pacific_date, get_fantasy_week

def get_tw_hour():
    tw_tz = pytz.timezone("Asia/Taipei")
    return datetime.now(tw_tz).hour

class StatsHandler(BaseHandler):
    def __init__(self):
        self.combined_pattern = re.compile(r"^#戰績$")
        self.daily_pattern = re.compile(r"^#當天戰績$")
        self.weekly_pattern = re.compile(r"^#當週戰績$")
        self.specific_week_pattern = re.compile(r"^#戰績W(\d+)$", re.IGNORECASE)
        self.specific_date_pattern = re.compile(r"^#戰績(\d{8})$")

    def parse_command(self, user_text: str) -> tuple[str | None, str | int | None]:
        if self.combined_pattern.match(user_text):
            return "combined", None
        elif self.daily_pattern.match(user_text):
            return "daily", None
        elif self.weekly_pattern.match(user_text):
            return "weekly", None
        
        m_week = self.specific_week_pattern.match(user_text)
        if m_week:
            return "specific_week", int(m_week.group(1))
            
        m_date = self.specific_date_pattern.match(user_text)
        if m_date:
            raw_date = m_date.group(1)
            return "specific_date", f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
            
        return None, None

    def can_handle(self, user_text: str) -> bool:
        cmd_type, _ = self.parse_command(user_text)
        return cmd_type is not None

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = event.message.text.strip()
        cmd_type, cmd_val = self.parse_command(user_text)
        
        if not cmd_type:
            return
            
        config = load_config()
        meta = load_league_metadata()
        today_pacific = get_pacific_date()
        is_offseason = meta.get('end_date') and today_pacific > meta['end_date']
        
        target_date = cmd_val if cmd_type == "specific_date" else today_pacific
        
        if cmd_type != "specific_week" and target_date > today_pacific:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="我不是未來人，無法提供未來數據")]))
            return

        if cmd_type != "specific_week" and meta.get('start_date') and target_date < meta['start_date']:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="查無當天數據")]))
            return

        is_undated_cmd = cmd_type in ["combined", "daily", "weekly"]
        if meta.get('end_date') and today_pacific > meta['end_date'] and is_undated_cmd:
            logging.info(f"[SYSTEM] 休賽季導向: {today_pacific} > {meta['end_date']}")
            target_date = meta['end_date']
            target_dt = pytz.timezone("US/Pacific").localize(datetime.strptime(target_date, "%Y-%m-%d"))
            target_week = get_fantasy_week(meta['start_date'], target_dt)
        else:
            target_dt = pytz.timezone("US/Pacific").localize(datetime.strptime(target_date, "%Y-%m-%d"))
            calculated_week = get_fantasy_week(meta.get('start_date') or config.get("DEFAULT_SEASON_START", "2025-10-21"), target_dt)
            if meta.get('end_week') and calculated_week > meta['end_week']:
                target_week = meta['end_week']
            else:
                target_week = cmd_val if cmd_type == "specific_week" else calculated_week

        if cmd_type != "specific_week" and meta.get('end_date') and target_date > meta['end_date']:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="查無當天數據")]))
            return
        
        if cmd_type == "combined":
            img_filename = f"{target_date}_combined.png"
            cache_key = f"{target_date}_combined"
        elif cmd_type in ["daily", "specific_date"]:
            img_filename = f"{target_date}_daily.png"
            cache_key = f"{target_date}_daily"
        else: # weekly, specific_week
            img_filename = f"week_{target_week}_weekly.png"
            cache_key = f"week_{target_week}_weekly"

        # Note: os.path.dirname is resolving from src/handlers/stats_handler.py, so we need to go up two levels to get to project root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        img_path = os.path.join(project_root, "data", "images", img_filename)
        
        if os.path.exists(img_path):
            logging.info(f"[CACHE] 命中圖片快取: {img_filename}")
            
            # Fetch SERVER_URL from env or config if needed, here we use os.getenv to mirror bot.py behavior safely
            SERVER_URL = os.getenv('SERVER_URL', 'http://localhost:5000')
            https_url = SERVER_URL.replace("http://", "https://")
            if not https_url.startswith("https://"):
                https_url = f"https://{https_url.lstrip('https://')}"
                
            img_url = f"{https_url}/images/{img_filename}"
            reply_img = ImageMessage(original_content_url=img_url, preview_image_url=img_url)
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[reply_img]))
            return

        if is_empty_data(cache_key):
            logging.info(f"[CACHE] 命中負向快取 (無數據): {cache_key}")
            err_msg = "查無當週數據" if "weekly" in cache_key else "查無當天數據"
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=err_msg)]))
            return

        is_current = cmd_type in ["combined", "daily", "weekly"]
        if is_current and not is_offseason and get_tw_hour() < 14:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="請於 14:00 後再進行查詢。")]))
            return
            
        lock_file = os.path.join(project_root, "data", f"{cache_key}_fetch.lock")
        os.makedirs(os.path.dirname(lock_file), exist_ok=True)
        try:
            fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
        except FileExistsError:
            logging.warning(f"[LOCK] 任務正在執行中，跳過重複請求: {cache_key}")
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="數據更新中")]))
            return

        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="數據更新中，請稍候再試...")]))
        
        env = os.environ.copy()
        env["FETCH_LOCK_PATH"] = lock_file
        env["TEST_DATE"] = target_date
        env["TEST_WEEK"] = str(target_week)
        
        logging.info(f"[TASK] 啟動背景更新任務 (main.py)，模式: {cmd_type}")
        subprocess.Popen([sys.executable, os.path.join(project_root, "main.py")], env=env)
```

- [ ] **Step 3: Run pytest to ensure module parses correctly**

Run: `pytest tests/handlers/test_stats_handler.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/handlers/stats_handler.py
git commit -m "feat(handlers): migrate execution logic into StatsHandler"
```

---

### Task 5: Refactor `bot.py` to use Dispatcher

**Files:**
- Modify: `bot.py`

- [ ] **Step 1: Write test (Run `bot.py` syntax check)**
We will refactor `bot.py` directly. The test is whether it runs without syntax errors.

- [ ] **Step 2: Clean up `bot.py`**
Remove old regex, `parse_command`, `get_tw_hour`, imports like `psutil`, `pytz`, `datetime`, and the entire body of `handle_message`. Instantiate Dispatcher and register `StatsHandler`.

Update `bot.py` structure:

```python
# Apply the diff to bot.py
import os
import sys
import psutil
import logging
import subprocess
from flask import Flask, request, abort, send_from_directory
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, SetWebhookEndpointRequest
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from dotenv import load_dotenv
from pyngrok import ngrok
from src.config import load_config
from src.fetcher import YahooFantasyFetcher
from src.cache_utils import save_league_metadata
from src.utils.token_utils import is_token_processed

# Import our new handlers
from src.handlers.dispatcher import CommandDispatcher
from src.handlers.stats_handler import StatsHandler

# ... (Keep cleanup_port, setup_ngrok, update_line_webhook as they are) ...
def cleanup_port(port):
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            for conns in proc.connections(kind='inet'):
                if conns.laddr.port == port:
                    logging.info(f"[SYSTEM] 發現佔用 Port {port} 的進程 (PID: {proc.pid})，正在關閉...")
                    proc.terminate()
                    proc.wait(timeout=3)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
            pass

def setup_ngrok(authtoken: str, port: int) -> str:
    """Start ngrok tunnel and return the public URL."""
    ngrok.set_auth_token(authtoken)
    tunnel = ngrok.connect(port)
    return tunnel.public_url

def update_line_webhook(configuration: Configuration, url: str):
    """Update the LINE Messaging API Webhook URL."""
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        endpoint = f"{url}/callback"
        set_webhook_request = SetWebhookEndpointRequest(endpoint=endpoint)
        try:
            line_bot_api.set_webhook_endpoint(set_webhook_request)
            line_bot_api.test_webhook_endpoint()
            logging.info(f"Successfully updated LINE Webhook URL to: {endpoint}")
        except Exception as e:
            logging.error(f"Failed to update LINE Webhook: {e}")

# Load env
load_dotenv()
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', 'dummy_secret')
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', 'dummy_token')
SERVER_URL = os.getenv('SERVER_URL', 'http://localhost:5000')

app = Flask(__name__)
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Initialize Dispatcher
dispatcher = CommandDispatcher()
dispatcher.register(StatsHandler())

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    logging.info(f"Request body: {body}")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@app.route("/images/<path:filename>")
def serve_image(filename):
    image_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "images")
    return send_from_directory(image_dir, filename)

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    if is_token_processed(event.reply_token):
        return

    user_text = event.message.text.strip()
    logging.info(f"[LINE] 收到指令: {user_text}")
    
    if user_text.startswith("#"):
        dispatcher.handle(event, configuration)

if __name__ == "__main__":
    cleanup_port(5001)
    config = load_config()
    fetcher = YahooFantasyFetcher(client_id=config.get("YAHOO_CLIENT_ID"), client_secret=config.get("YAHOO_CLIENT_SECRET"))
    try:
        logging.info("[SYSTEM] 同步賽季中繼資料...")
        meta = fetcher.fetch_league_metadata(config["LEAGUE_ID"])
        save_league_metadata(meta)
    except Exception as e:
        logging.error(f"[SYSTEM] 賽季資料同步失敗: {e}")

    port = 5001

    if config.get("NGROK_AUTHTOKEN"):
        logging.info("NGROK_AUTHTOKEN found. Starting automated setup...")
        try:
            public_url = setup_ngrok(config["NGROK_AUTHTOKEN"], port)
            SERVER_URL = public_url
            os.environ['SERVER_URL'] = public_url # Pass down to subprocesses
            logging.info(f"ngrok tunnel opened at: {public_url}")
            update_line_webhook(configuration, public_url)
        except Exception as e:
            logging.error(f"ngrok setup failed: {e}")
            logging.info("Falling back to manual SERVER_URL.")
    else:
        logging.info("No NGROK_AUTHTOKEN found. Using existing SERVER_URL.")

    app.run(host="0.0.0.0", port=port)
```

- [ ] **Step 3: Run end-to-end tests**

Run: `python3 test_client_e2e.py`
Expected: Output showing Webhook success (200), bot preparing replies ("數據更新中" or Images), and subprocess triggered without errors.

- [ ] **Step 4: Commit**

```bash
git add bot.py
git commit -m "refactor: decouple bot routing logic to CommandDispatcher"
```
