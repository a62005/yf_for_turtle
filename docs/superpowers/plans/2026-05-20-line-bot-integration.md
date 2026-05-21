# LINE Bot Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Flask server to act as a LINE Bot webhook and image host, routing requests for Yahoo Fantasy stats with caching, negative caching, and strict time-based fetching rules.

**Architecture:** 
1. Create `src/cache_utils.py` to handle negative caching (`empty_records.json`).
2. Create a `bot.py` containing the Flask app and LINE Bot SDK setup. 
3. Parse commands via Regex.
4. Check cache (`data/images/` or `data/empty_records.json`).
5. Enforce time rules (UTC+8 00:00-14:00 restriction).
6. Trigger `main.py` as a subprocess when needed, and update `main.py` to record empty states.

**Tech Stack:** Python, Flask, line-bot-sdk.

---

### Task 1: Negative Caching Helper

**Files:**
- Create: `src/cache_utils.py`
- Test: `tests/test_cache_utils.py`

- [ ] **Step 1: Write the failing test**
Create `tests/test_cache_utils.py` to test reading and writing cache.
```python
import os
import json
import pytest
from src.cache_utils import is_empty_data, mark_empty_data, CACHE_FILE

@pytest.fixture(autouse=True)
def clean_cache():
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
    yield
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)

def test_cache_operations():
    assert is_empty_data("test_key") is False
    mark_empty_data("test_key")
    assert is_empty_data("test_key") is True
```

- [ ] **Step 2: Run test to verify it fails**
Run: `PYTHONPATH=. pytest tests/test_cache_utils.py -v`
Expected: FAIL with ModuleNotFoundError or ImportError

- [ ] **Step 3: Write minimal implementation**
Create `src/cache_utils.py`.
```python
import os
import json

CACHE_FILE = os.path.join("data", "empty_records.json")

def _load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_cache(data):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)

def is_empty_data(key: str) -> bool:
    cache = _load_cache()
    return cache.get(key, False)

def mark_empty_data(key: str):
    cache = _load_cache()
    cache[key] = True
    _save_cache(cache)
```

- [ ] **Step 4: Run test to verify it passes**
Run: `PYTHONPATH=. pytest tests/test_cache_utils.py -v`
Expected: PASS

- [ ] **Step 5: Commit Cache Utils**
```bash
git add src/cache_utils.py tests/test_cache_utils.py
git commit -m "feat: add negative caching utilities"
```

---

### Task 2: Setup Flask App and Basic LINE Bot Webhook

**Files:**
- Create: `bot.py`
- Modify: `requirements.txt`
- Modify: `.env.example`

- [ ] **Step 1: Add dependencies**
Update `requirements.txt` to include `flask` and `line-bot-sdk`.
```txt
yahoofantasy
python-dotenv
pytest
pytest-mock
pytz
Jinja2
playwright
flask
line-bot-sdk
```

- [ ] **Step 2: Add env vars to `.env.example`**
Update `.env.example` to include LINE credentials and an optional server URL.
```env
LEAGUE_ID=your_league_id_here
TEAM_MAPPING_FILE=team_mapping.json
SEASON_START_DATE=2025-10-21
YAHOO_CLIENT_ID=your_yahoo_client_id
YAHOO_CLIENT_SECRET=your_yahoo_client_secret
LINE_CHANNEL_SECRET=your_line_channel_secret
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token
SERVER_URL=https://your-ngrok-url.ngrok-free.app
```

- [ ] **Step 3: Write basic Flask + LINE Bot structure**
Create `bot.py` with the boilerplate to verify webhooks.
```python
import os
import logging
from flask import Flask, request, abort, send_from_directory
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from dotenv import load_dotenv

# Load env
load_dotenv()
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', 'dummy_secret')
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', 'dummy_token')
SERVER_URL = os.getenv('SERVER_URL', 'http://localhost:5000')

app = Flask(__name__)
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

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
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        reply_req = ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text="Webhook received")]
        )
        try:
            line_bot_api.reply_message(reply_req)
        except Exception as e:
            logging.error(f"Failed to reply: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
```

- [ ] **Step 4: Commit dependencies and basic bot structure**
```bash
git add requirements.txt .env.example bot.py
git commit -m "feat: setup basic Flask app, image route, and LINE bot webhook"
```

---

### Task 3: Regex Command Parser & Logic Orchestration

**Files:**
- Modify: `bot.py`

- [ ] **Step 1: Implement `handle_message` logic in `bot.py`**
Replace the dummy reply in `handle_message` with the actual Regex parsing, caching checks, time gating, and subprocess execution.
```python
# In bot.py, add imports at the top
import re
import subprocess
from datetime import datetime
import pytz
from linebot.v3.messaging import ImageMessage
from src.cache_utils import is_empty_data
from src.utils.time_utils import get_pacific_date, get_fantasy_week
from src.config import load_config

def get_tw_hour():
    tw_tz = pytz.timezone("Asia/Taipei")
    return datetime.now(tw_tz).hour

# Replace handle_message with this:
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_text = event.message.text.strip()
    
    # Regex patterns
    combined_pattern = re.compile(r"^#戰績$")
    daily_pattern = re.compile(r"^#當天戰績$")
    weekly_pattern = re.compile(r"^#當週戰績$")
    specific_week_pattern = re.compile(r"^#戰績W(\d+)$", re.IGNORECASE)
    specific_date_pattern = re.compile(r"^#戰績(\d{8})$")
    
    cmd_type = None
    cmd_val = None
    
    if combined_pattern.match(user_text):
        cmd_type = "combined"
    elif daily_pattern.match(user_text):
        cmd_type = "daily"
    elif weekly_pattern.match(user_text):
        cmd_type = "weekly"
    else:
        m_week = specific_week_pattern.match(user_text)
        if m_week:
            cmd_type = "specific_week"
            cmd_val = int(m_week.group(1))
        else:
            m_date = specific_date_pattern.match(user_text)
            if m_date:
                cmd_type = "specific_date"
                raw_date = m_date.group(1)
                cmd_val = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
                
    if not cmd_type:
        return # Ignore non-matching messages

    config = load_config()
    current_date = get_pacific_date()
    current_week = get_fantasy_week(config.get("SEASON_START_DATE", "2025-10-21"))
    
    target_date = cmd_val if cmd_type == "specific_date" else current_date
    target_week = cmd_val if cmd_type == "specific_week" else current_week
    
    # Determine expected filenames and cache keys based on command
    if cmd_type == "combined":
        img_filename = f"{target_date}_combined.png"
        cache_key = f"{target_date}_combined"
    elif cmd_type in ["daily", "specific_date"]:
        img_filename = f"{target_date}_daily.png"
        cache_key = f"{target_date}_daily"
    else: # weekly, specific_week
        img_filename = f"week_{target_week}_weekly.png"
        cache_key = f"week_{target_week}_weekly"

    img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "images", img_filename)
    
    # Step 1: Check standard cache (Image exists)
    if os.path.exists(img_path):
        img_url = f"{SERVER_URL}/images/{img_filename}"
        reply_img = ImageMessage(original_content_url=img_url, preview_image_url=img_url)
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[reply_img]))
        return

    # Step 1.5: Check negative cache
    if is_empty_data(cache_key):
        err_msg = "查無當週數據" if "weekly" in cache_key else "查無當天數據"
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=err_msg)]))
        return

    # Step 2: Time Gate for current period
    is_current = cmd_type in ["combined", "daily", "weekly"]
    if is_current and get_tw_hour() < 14:
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="請於 14:00 後再進行查詢。")]))
        return
        
    # Step 3: Trigger main.py fetch
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="數據更新中，請稍候再試...")]))
    
    # Spawn subprocess
    env = os.environ.copy()
    if cmd_type == "specific_date":
        env["TEST_DATE"] = target_date
    elif cmd_type == "specific_week":
        env["TEST_WEEK"] = str(target_week)
        
    subprocess.Popen(["python3", "main.py"], env=env)
```

- [ ] **Step 2: Commit Command Parser**
```bash
git add bot.py
git commit -m "feat: implement regex parser, dual cache logic, and subprocessing"
```

---

### Task 4: Main.py Empty State Recording

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Update `main.py` to record empty cache**
If `daily_stats` or `weekly_stats` is completely empty, it should call `mark_empty_data`.
```python
# In main.py
# Add import at top
from src.cache_utils import mark_empty_data

# ... in weekly section, after fetch_weekly_stats
        if not weekly_stats.get("team_stats"):
            logging.warning(f"No weekly stats found for Week {current_week}")
            mark_empty_data(f"week_{current_week}_weekly")

# ... in daily section, after fetch_daily_stats
        if not daily_stats.get("team_stats"):
            logging.warning(f"No daily stats found for {today_str}")
            mark_empty_data(f"{today_str}_daily")
            mark_empty_data(f"{today_str}_combined")
```

- [ ] **Step 2: Verify compilation**
Run `python3 -m py_compile main.py` to ensure syntax is correct.

- [ ] **Step 3: Commit Main integration**
```bash
git add main.py
git commit -m "feat: record empty data state in main execution flow"
```
