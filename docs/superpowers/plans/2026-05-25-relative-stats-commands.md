# Relative Stats Commands and Unified Image Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify stats image generation to combined only, add support for `#戰績昨天` and `#戰績上週`, and implement dynamic fetching/caching for week end dates to resolve out-of-bounds week errors.

**Architecture:** Add lazy-loading logic for week metadata in `src/fetcher.py` and `src/cache_utils.py`. Consolidate command regex matching and processing in `src/handlers/stats_handler.py`. Fallback cleanly for invalid week queries.

**Tech Stack:** Python 3, `pytest`, `re`, `yahoofantasy`.

---

### Task 1: Add `fetch_week_end_date` to Fetcher

**Files:**
- Modify: `src/fetcher.py`
- Test: `tests/test_fetcher.py`

- [ ] **Step 1: Write the failing test**
Modify `tests/test_fetcher.py` to add `test_fetch_week_end_date`.

```python
def test_fetch_week_end_date(mocker):
    from src.fetcher import YahooFantasyFetcher
    mock_ctx = mocker.patch("yahoofantasy.Context")
    
    mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <fantasy_content xml:lang="en-US" yahoo:uri="http://fantasysports.yahooapis.com/fantasy/v2/league/12345/scoreboard;week=16" xmlns:yahoo="http://www.yahooapis.com/v1/base.rng" xmlns="http://fantasysports.yahooapis.com/fantasy/v2/base.rng">
      <league>
        <scoreboard>
          <matchups>
            <matchup>
              <week>16</week>
              <week_start>2025-02-03</week_start>
              <week_end>2025-02-09</week_end>
            </matchup>
          </matchups>
        </scoreboard>
      </league>
    </fantasy_content>
    """
    mock_ctx.return_value.make_request.return_value = mock_xml
    
    fetcher = YahooFantasyFetcher("12345")
    fetcher.ctx = mock_ctx.return_value
    
    # Assert successful parsing
    end_date = fetcher.fetch_week_end_date("12345", 16)
    assert end_date == "2025-02-09"
    
    # Test error handling (missing matchup)
    mock_error_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <fantasy_content xmlns="http://fantasysports.yahooapis.com/fantasy/v2/base.rng">
      <league><scoreboard><matchups></matchups></scoreboard></league>
    </fantasy_content>"""
    mock_ctx.return_value.make_request.return_value = mock_error_xml
    end_date_err = fetcher.fetch_week_end_date("12345", 16)
    assert end_date_err is None
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_fetcher.py::test_fetch_week_end_date -v`
Expected: FAIL with "AttributeError: 'YahooFantasyFetcher' object has no attribute 'fetch_week_end_date'"

- [ ] **Step 3: Write minimal implementation**
Add `fetch_week_end_date` to `src/fetcher.py` (e.g., around line 68).

```python
    def fetch_week_end_date(self, league_id: str, week: int) -> str | None:
        """Fetch the end date for a specific week from the scoreboard."""
        league_id = self._normalize_league_id(league_id)
        url = f"league/{league_id}/scoreboard;week={week}"
        try:
            import xml.etree.ElementTree as ET
            import logging
            data = self.ctx.make_request(url)
            root = ET.fromstring(data)
            ns = {'ns': 'http://fantasysports.yahooapis.com/fantasy/v2/base.rng'}
            matchup_node = root.find('.//ns:matchups/ns:matchup', ns)
            if matchup_node is not None:
                end_node = matchup_node.find('ns:week_end', ns)
                if end_node is not None:
                    return end_node.text
            return None
        except Exception as e:
            import logging
            logging.error(f"Failed to fetch week end date for week {week}: {e}")
            return None
```

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_fetcher.py::test_fetch_week_end_date -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add tests/test_fetcher.py src/fetcher.py
git commit -m "feat: add fetch_week_end_date to fetcher"
```

---

### Task 2: Refactor `StatsHandler` command parsing and logic

**Files:**
- Modify: `src/handlers/stats_handler.py`
- Test: `tests/handlers/test_stats_handler.py`

- [ ] **Step 1: Update Tests for Pattern Matching**
Modify `tests/handlers/test_stats_handler.py` to include tests for `#戰績昨天` and `#戰績上週`. Remove tests for `#當天戰績` and `#當週戰績` if they exist.

```python
def test_stats_handler_regex_patterns():
    from src.handlers.stats_handler import StatsHandler
    handler = StatsHandler()
    
    assert handler.can_handle("#戰績") is True
    assert handler.can_handle("#戰績昨天") is True
    assert handler.can_handle("#戰績上週") is True
    assert handler.can_handle("#戰績W23") is True
    assert handler.can_handle("#戰績20250101") is True
    assert handler.can_handle("#當天戰績") is False # Removed
    
    assert handler.parse_command("#戰績") == ("combined", None)
    assert handler.parse_command("#戰績昨天") == ("yesterday", None)
    assert handler.parse_command("#戰績上週") == ("last_week", None)
    assert handler.parse_command("#戰績W23") == ("specific_week", 23)
    assert handler.parse_command("#戰績20250101") == ("specific_date", "2025-01-01")
```

- [ ] **Step 2: Run parsing tests to see them fail**
Run: `pytest tests/handlers/test_stats_handler.py -v`
Expected: FAIL due to missing regex patterns for 昨天 and 上週.

- [ ] **Step 3: Update `StatsHandler.parse_command`**
Update `src/handlers/stats_handler.py`:

```python
    def __init__(self):
        self.combined_pattern = re.compile(r"^#戰績$")
        self.yesterday_pattern = re.compile(r"^#戰績昨天$")
        self.last_week_pattern = re.compile(r"^#戰績上週$")
        self.specific_week_pattern = re.compile(r"^#戰績W(\d+)$", re.IGNORECASE)
        self.specific_date_pattern = re.compile(r"^#戰績(\d{8})$")

    def parse_command(self, user_text: str) -> tuple[str | None, str | int | None]:
        if self.combined_pattern.match(user_text):
            return "combined", None
        elif self.yesterday_pattern.match(user_text):
            return "yesterday", None
        elif self.last_week_pattern.match(user_text):
            return "last_week", None
            
        m_week = self.specific_week_pattern.match(user_text)
        if m_week:
            return "specific_week", int(m_week.group(1))
            
        m_date = self.specific_date_pattern.match(user_text)
        if m_date:
            raw_date = m_date.group(1)
            return "specific_date", f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
            
        return None, None
```

- [ ] **Step 4: Run parsing tests to verify they pass**
Run: `pytest tests/handlers/test_stats_handler.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add src/handlers/stats_handler.py tests/handlers/test_stats_handler.py
git commit -m "feat: add support for relative stats command parsing"
```

---

### Task 3: Implement Metadata Lazy-Loading in Handler

**Files:**
- Modify: `src/handlers/stats_handler.py`

- [ ] **Step 1: Write helper for lazy loading week end date**
In `src/handlers/stats_handler.py`, add a helper function `_get_week_end_date` inside or outside the class. Note: `save_league_metadata` needs to be imported from `src.cache_utils`. Also need to import `load_config` and `YahooFantasyFetcher`.

```python
from src.cache_utils import load_league_metadata, save_league_metadata, is_empty_data
from src.fetcher import YahooFantasyFetcher
from src.config import load_config
from datetime import timedelta # Ensure timedelta is imported

# Inside StatsHandler class (or outside, but needs fetcher)
    def _get_week_end_date(self, week: int) -> str | None:
        meta = load_league_metadata()
        week_str = str(week)
        if "week_dates" in meta and week_str in meta["week_dates"]:
            return meta["week_dates"][week_str]
        
        config = load_config()
        fetcher = YahooFantasyFetcher(config["LEAGUE_ID"])
        end_date = fetcher.fetch_week_end_date(config["LEAGUE_ID"], week)
        
        if end_date:
            if "week_dates" not in meta:
                meta["week_dates"] = {}
            meta["week_dates"][week_str] = end_date
            save_league_metadata(meta)
        return end_date
```

- [ ] **Step 2: Update `StatsHandler.execute` logic**
Update the massive `execute` method in `src/handlers/stats_handler.py` to use unified combined images and relative time logic.

```python
    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = event.message.text.strip()
        cmd_type, cmd_val = self.parse_command(user_text)
        
        if not cmd_type:
            return
            
        config = load_config()
        meta = load_league_metadata()
        today_pacific = get_pacific_date()
        today_dt = pytz.timezone("US/Pacific").localize(datetime.strptime(today_pacific, "%Y-%m-%d"))
        
        is_offseason = meta.get('end_date') and today_pacific > meta['end_date']
        
        # Calculate target_date and target_week based on cmd_type
        target_date = None
        target_week = None
        
        start_date = meta.get('start_date') or config.get("DEFAULT_SEASON_START", "2025-10-21")
        
        if cmd_type == "specific_date":
            target_date = cmd_val
            target_dt = pytz.timezone("US/Pacific").localize(datetime.strptime(target_date, "%Y-%m-%d"))
            target_week = get_fantasy_week(start_date, target_dt)
        elif cmd_type == "specific_week":
            target_week = cmd_val
        elif cmd_type == "yesterday":
            target_dt = today_dt - timedelta(days=1)
            target_date = target_dt.strftime("%Y-%m-%d")
            target_week = get_fantasy_week(start_date, target_dt)
        elif cmd_type == "last_week":
            current_week = get_fantasy_week(start_date, today_dt)
            target_week = max(1, current_week - 1)
        elif cmd_type == "combined":
            # Default #戰績 logic
            target_date = today_pacific
            if is_offseason:
                logging.info(f"[SYSTEM] 休賽季導向: {today_pacific} > {meta['end_date']}")
                target_date = meta['end_date']
            target_dt = pytz.timezone("US/Pacific").localize(datetime.strptime(target_date, "%Y-%m-%d"))
            target_week = get_fantasy_week(start_date, target_dt)
            if meta.get('end_week') and target_week > meta['end_week']:
                target_week = meta['end_week']
                
        # Validate week limits (fix for out-of-bounds bug)
        if target_week is not None and meta.get('end_week'):
            if target_week > meta['end_week'] or target_week < 1:
                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="查無當週戰績")]))
                return
                
        # Lazy load date for week queries if date isn't set yet
        if not target_date and target_week:
            fetched_date = self._get_week_end_date(target_week)
            if not fetched_date:
                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="查無當週戰績")]))
                return
            target_date = fetched_date

        # Future date guard
        if cmd_type != "specific_week" and cmd_type != "last_week" and target_date > today_pacific:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="我不是未來人，無法提供未來數據")]))
            return

        # Past date guard
        if meta.get('start_date') and target_date < meta['start_date']:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="查無當天數據")]))
            return

        # Unified image cache key
        img_filename = f"{target_date}_combined.png"
        cache_key = f"{target_date}_combined"

        # The rest is the same standard cache checking/execution
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        img_path = os.path.join(project_root, "data", "images", img_filename)
        
        if os.path.exists(img_path):
            logging.info(f"[CACHE] 命中圖片快取: {img_filename}")
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
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="查無當天數據")]))
            return

        is_current = cmd_type == "combined"
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
        # Force combined mode in env if needed by main.py
        env["MODE"] = "combined" 
        
        logging.info(f"[TASK] 啟動背景更新任務 (main.py)，模式: combined")
        subprocess.Popen([sys.executable, os.path.join(project_root, "main.py")], env=env)
```

- [ ] **Step 3: Run `pytest tests/handlers/test_stats_handler.py -v` (Optional fixes)**
Fix any broken test assertions in `test_stats_handler.py` relating to `execute` if they assert the old `img_filename`. You may need to mock `_get_week_end_date` in the execute tests.

- [ ] **Step 4: Commit**
```bash
git add src/handlers/stats_handler.py
git commit -m "feat: implement week end date lazy-loading and unify images"
```

---
