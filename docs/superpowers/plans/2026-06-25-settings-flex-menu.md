# 設置選單與多聯盟目錄隔離實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 實現動態配置 `LEAGUE_ID` 以及進行聯賽資料（快取、圖片、對應表）的 `data/league/<LEAGUE_ID>/` 目錄物理隔離，並實作全新的 `#設置` Flex 選單與 `#設置聯盟ID <ID>` 指令。

**Architecture:** 
1. 建立 `path_utils` 模組動態輸出基於當前 `LEAGUE_ID` 的物理隔離路徑，並改寫 `cache_utils` 與圖片儲存邏輯。
2. 重構 `bot.py` 與 `config.py`，支援在未設定 `LEAGUE_ID` 下的容錯空載啟動。
3. 實作 `SettingsHandler` 提供動態 Flex 按鈕選單，以及 `SetLeagueIdHandler` 執行即時 API 驗證與寫入設定。

**Tech Stack:** Python 3, pytest, unittest.mock, linebot-sdk-v3

---

### Task 1: 執行舊檔案清理與實作 PathUtils 模組

**Files:**
- Create: `src/utils/path_utils.py`
- Modify: `src/utils/cache_utils.py`
- Create: `tests/test_path_utils.py`
- Create/Delete: `scripts/cleanup_old_files.py` (暫時清理腳本)

- [ ] **Step 1: 撰寫並執行舊檔案清理腳本**

在專案根目錄下建立一個臨時腳本 `scripts/cleanup_old_files.py`：
```python
import os
import glob

# 刪除全域舊配置與快取
files_to_remove = [
    "data/empty_records.json",
    "data/league_metadata.json",
    "team_mapping.json"
]
for f in files_to_remove:
    if os.path.exists(f):
        os.remove(f)
        print(f"Removed old file {f}")

# 刪除舊的快取圖片 (保留 bonus.png 獎金圖)
image_dir = "data/images"
if os.path.exists(image_dir):
    for f in glob.glob(os.path.join(image_dir, "*")):
        if os.path.basename(f) != "bonus.png":
            if os.path.isfile(f):
                os.remove(f)
                print(f"Removed cache image {f}")
```
執行命令：`.venv\Scripts\python scripts/cleanup_old_files.py`
Expected: 輸出被刪除的檔案與快取路徑。
執行成功後，將該臨時腳本手動刪除：`rm scripts/cleanup_old_files.py`。

- [ ] **Step 2: 撰寫 PathUtils 與快取適配的單元測試**

在 `tests/test_path_utils.py` 中寫入以下測試：
```python
import os
import pytest
from unittest.mock import patch
from src.utils.path_utils import (
    get_league_id, 
    get_league_dir, 
    get_league_metadata_path,
    get_league_team_mapping_path
)

def test_path_utils_dynamic_routing():
    # 測試 A: 當 config 中沒有 LEAGUE_ID 時
    with patch("src.utils.path_utils.load_config", return_value={}):
        assert get_league_id() is None
        assert "default" in get_league_dir()
        
    # 測試 B: 當 config 中有 LEAGUE_ID 時，返回正確物理隔離路徑
    with patch("src.utils.path_utils.load_config", return_value={"LEAGUE_ID": "99999"}):
        assert get_league_id() == "99999"
        assert get_league_dir().replace("\\", "/").endswith("data/league/99999")
        assert get_league_metadata_path().replace("\\", "/").endswith("data/league/99999/metadata.json")
        assert get_league_team_mapping_path().replace("\\", "/").endswith("data/league/99999/team_mapping.json")
```

- [ ] **Step 3: 執行測試確認其失敗**

Run: `.venv\Scripts\python -m pytest tests/test_path_utils.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 4: 實作 PathUtils 並修改 CacheUtils 適配動態路徑**

建立 `src/utils/path_utils.py`：
```python
import os

# 根目錄 C:\Users\HsiehLink\Python\yf_for_turtle
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

def get_league_id() -> str | None:
    """動態獲取當前配置的聯盟 ID，優先從 JSON 載入，否則從環境變數載入。"""
    from src.config import load_config
    return load_config().get("LEAGUE_ID")

def get_league_dir(league_id: str = None) -> str:
    lid = league_id or get_league_id() or "default"
    return os.path.join(BASE_DIR, "data", "league", str(lid))

def get_league_metadata_path(league_id: str = None) -> str:
    return os.path.join(get_league_dir(league_id), "metadata.json")

def get_league_empty_records_path(league_id: str = None) -> str:
    return os.path.join(get_league_dir(league_id), "empty_records.json")

def get_league_team_mapping_path(league_id: str = None) -> str:
    return os.path.join(get_league_dir(league_id), "team_mapping.json")

def get_league_image_dir(league_id: str = None) -> str:
    return os.path.join(get_league_dir(league_id), "image")

def get_league_daily_dir(league_id: str = None) -> str:
    return os.path.join(get_league_dir(league_id), "daily")

def get_league_weekly_dir(league_id: str = None) -> str:
    return os.path.join(get_league_dir(league_id), "weekly")
```

修改 `src/utils/cache_utils.py` 中所有的路徑讀寫，引進 `path_utils`：
```python
import os
import json
from datetime import datetime
from filelock import FileLock
from src.utils.path_utils import get_league_metadata_path, get_league_empty_records_path

def _load_cache(file_path):
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}

def _save_cache(data, file_path):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    temp_file = file_path + '.tmp'
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(temp_file, file_path)

def is_empty_data(key: str) -> bool:
    path = get_league_empty_records_path()
    cache = _load_cache(path)
    return cache.get(key, False)

def mark_empty_data(key: str):
    path = get_league_empty_records_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with FileLock(path + ".lock"):
        cache = _load_cache(path)
        cache[key] = True
        _save_cache(cache, path)

def save_league_metadata(data: dict):
    """Save league metadata with a timestamp."""
    path = get_league_metadata_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with FileLock(path + ".lock"):
        data["last_updated"] = datetime.now().isoformat()
        _save_cache(data, path)

def load_league_metadata() -> dict:
    """Load league metadata from cache."""
    return _load_cache(get_league_metadata_path())
```

- [ ] **Step 5: 執行測試確認通過**

Run: `.venv\Scripts\python -m pytest tests/test_path_utils.py -v`
Expected: PASS

- [ ] **Step 6: 提交變更**

首先執行 git 分支檢查保護機制，確認我們不在 `dev` 或 `master`：
Run: `git branch --show-current`
Expected: `feat/settings-flex-menu`
若確認無誤，執行提交：
```bash
git add src/utils/path_utils.py src/utils/cache_utils.py tests/test_path_utils.py
git commit -m "feat: implement path_utils and adapt cache_utils for multi-league isolation"
```

---

### Task 2: 修改 config.py 與 bot.py 支援容錯啟動

**Files:**
- Modify: `src/config.py`
- Modify: `bot.py`
- Create: `tests/test_bot_tolerance.py`

- [ ] **Step 1: 撰寫容錯啟動與配置覆蓋的單元測試**

在 `tests/test_bot_tolerance.py` 中寫入以下測試：
```python
import os
import json
import pytest
from unittest.mock import patch
from src.config import load_config

def test_load_config_with_dynamic_override(tmp_path):
    # 測試配置覆蓋優先權
    sec_dir = tmp_path / "data" / "security"
    sec_dir.mkdir(parents=True)
    config_file = sec_dir / "league_config.json"
    
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump({"LEAGUE_ID": "88888"}, f)
        
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", pytest.mock_open(read_data='{"LEAGUE_ID": "88888"}')):
        config = load_config()
        assert config["LEAGUE_ID"] == "88888"
```

- [ ] **Step 2: 執行測試確認其失敗**

Run: `.venv\Scripts\python -m pytest tests/test_bot_tolerance.py -v`
Expected: FAIL (AssertionError 或 ValueError)

- [ ] **Step 3: 修改 config.py 支援 JSON 載入與容錯**

修改 `src/config.py`，移除 `ValueError` 拋出，並新增讀取 `league_config.json` 邏輯：
```python
import os
import json
from dotenv import load_dotenv

def load_config() -> dict:
    dynamic_server_url = os.environ.get("SERVER_URL")
    
    load_dotenv("league.env", encoding="utf-8")
    load_dotenv(".env", override=True, encoding="utf-8")
    
    current_server_url = os.environ.get("SERVER_URL")
    if (not current_server_url or current_server_url.strip() == "") and dynamic_server_url:
        os.environ["SERVER_URL"] = dynamic_server_url
    
    # 讀取環境變數
    league_id = os.getenv("LEAGUE_ID")
    
    # 優先讀取動態設定 data/security/league_config.json
    security_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "security", "league_config.json"))
    if os.path.exists(security_file):
        try:
            with open(security_file, "r", encoding="utf-8") as f:
                sec_data = json.load(f)
                if sec_data.get("LEAGUE_ID"):
                    league_id = str(sec_data["LEAGUE_ID"])
        except Exception:
            pass
            
    mapping_file = os.getenv("TEAM_MAPPING_FILE", "team_mapping.json")
    season_start = os.getenv("SEASON_START_DATE")
    
    return {
        "LEAGUE_ID": league_id, # 可以為 None
        "TEAM_MAPPING_FILE": mapping_file,
        "SEASON_START_DATE": season_start,
        "YAHOO_CLIENT_ID": os.getenv("YAHOO_CLIENT_ID"),
        "YAHOO_CLIENT_SECRET": os.getenv("YAHOO_CLIENT_SECRET"),
        "NGROK_AUTHTOKEN": os.getenv("NGROK_AUTHTOKEN"),
        "LINE_CHANNEL_SECRET": os.getenv("LINE_CHANNEL_SECRET"),
        "LINE_CHANNEL_ACCESS_TOKEN": os.getenv("LINE_CHANNEL_ACCESS_TOKEN"),
        "SERVER_URL": os.getenv("SERVER_URL"),
        "LLM_API_KEY": os.getenv("LLM_API_KEY"),
        "LLM_MODEL": os.getenv("LLM_MODEL"),
        "NEXT_SEASON_START_DATE": os.getenv("NEXT_SEASON_START_DATE"),
        "DRAFT_DATE": os.getenv("DRAFT_DATE"),
        "PRIZE_IMAGE_PATH": os.getenv("PRIZE_IMAGE_PATH"),
        "ENABLE_FOOTBALL_ANALYSIS": os.getenv("ENABLE_FOOTBALL_ANALYSIS", "False").lower() in ("true", "1", "yes")
    }
```

- [ ] **Step 4: 修改 bot.py 容錯啟動與圖片路徑動態化**

修改 `bot.py` 的 `serve_image` 函數，依據當前 `LEAGUE_ID` 動態尋找圖片目錄：
```python
@app.route("/images/<path:filename>")
def serve_image(filename):
    from src.utils.path_utils import get_league_image_dir
    image_dir = get_league_image_dir()
    return send_from_directory(image_dir, filename)
```

並修改 `bot.py` 底部 `__main__` 初始化段落：
```python
if __name__ == "__main__":
    cleanup_port(5001)
    config = load_config()
    
    league_id = config.get("LEAGUE_ID")
    if league_id:
        fetcher = YahooFantasyFetcher(
            client_id=config.get("YAHOO_CLIENT_ID"), 
            client_secret=config.get("YAHOO_CLIENT_SECRET")
        )
        try:
            from src.utils.season_utils import sync_season_metadata
            sync_season_metadata(fetcher, league_id)
        except Exception as e:
            logging.error(f"[SYSTEM] 賽季資料同步失敗: {e}")
    else:
        logging.warning("[SYSTEM] 聯賽 ID (LEAGUE_ID) 尚未配置，將跳過啟動時的賽季資料同步。請透過 LINE 設置。")

    app.run(host="0.0.0.0", port=5001)
```

- [ ] **Step 5: 執行測試確認通過**

Run: `.venv\Scripts\python -m pytest tests/test_bot_tolerance.py -v`
Expected: PASS

- [ ] **Step 6: 提交變更**

首先執行 git 分支檢查保護機制：
Run: `git branch --show-current`
Expected: `feat/settings-flex-menu`
若確認無誤，執行提交：
```bash
git add src/config.py bot.py tests/test_bot_tolerance.py
git commit -m "refactor: support tolerance startup and dynamic config loading from JSON"
```

---

### Task 3: fetcher.py 自訂數據快取重構

**Files:**
- Modify: `src/fetcher.py`
- Create: `tests/test_fetcher_cache_isolation.py`

- [ ] **Step 1: 撰寫自訂數據快取路徑的單元測試**

在 `tests/test_fetcher_cache_isolation.py` 中寫入以下測試：
```python
import os
import json
import pytest
from unittest.mock import MagicMock, patch
from src.fetcher import YahooFantasyFetcher

def test_fetcher_weekly_stats_saves_to_league_dir(tmp_path):
    fetcher = YahooFantasyFetcher(client_id="dummy", client_secret="dummy")
    
    # Mock Context 的 make_request 回傳
    mock_data = {"test_stats": "data"}
    fetcher.ctx.make_request = MagicMock(return_value=mock_data)
    
    # Mock get_league_weekly_dir 指向 tmp_path
    with patch("src.fetcher.get_league_weekly_dir", return_value=str(tmp_path)):
        res = fetcher.fetch_weekly_stats("18457", 5)
        
        assert res == mock_data
        cache_path = tmp_path / "week_5.json"
        assert cache_path.exists()
        
        # 驗證快取命中
        fetcher.ctx.make_request.reset_mock()
        res_cached = fetcher.fetch_weekly_stats("18457", 5)
        assert res_cached == mock_data
        fetcher.ctx.make_request.assert_not_called()
```

- [ ] **Step 2: 執行測試並確認其失敗**

Run: `.venv\Scripts\python -m pytest tests/test_fetcher_cache_isolation.py -v`
Expected: FAIL (AssertionError 或是找不到該模組)

- [ ] **Step 3: 實作自訂 JSON 快取載入與寫入**

在 `src/fetcher.py` 頂部加入導入：
```python
import os
import json
from src.utils.path_utils import get_league_weekly_dir, get_league_daily_dir
```

並修改 `src/fetcher.py` 的 `fetch_weekly_stats` 與 `fetch_daily_stats` 方法（取代原先的私有快取 `_load_or_fetch`）：
```python
    def fetch_weekly_stats(self, league_id: str, week: int) -> dict:
        league_id = self._normalize_league_id(league_id)
        raw_id = league_id.split(".")[-1]
        
        cache_dir = get_league_weekly_dir(raw_id)
        cache_path = os.path.join(cache_dir, f"week_{week}.json")
        
        if os.path.exists(cache_path):
            logging.info(f"[CACHE] 命中週數據快取: {cache_path}")
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
                
        url = f"league/{league_id}/scoreboard;week={week}"
        data = self.ctx.make_request(url)
        
        os.makedirs(cache_dir, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data

    def fetch_daily_stats(self, league_id: str, date_str: str) -> dict:
        league_id = self._normalize_league_id(league_id)
        raw_id = league_id.split(".")[-1]
        
        cache_dir = get_league_daily_dir(raw_id)
        cache_path = os.path.join(cache_dir, f"date_{date_str}.json")
        
        if os.path.exists(cache_path):
            logging.info(f"[CACHE] 命中日數據快取: {cache_path}")
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
                
        url = f"league/{league_id}/teams/stats;type=date;date={date_str}"
        data = self.ctx.make_request(url)
        
        os.makedirs(cache_dir, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data
```

- [ ] **Step 4: 執行測試確認通過**

Run: `.venv\Scripts\python -m pytest tests/test_fetcher_cache_isolation.py -v`
Expected: PASS

- [ ] **Step 5: 提交變更**

首先執行 git 分支檢查保護機制：
Run: `git branch --show-current`
Expected: `feat/settings-flex-menu`
若確認無誤，執行提交：
```bash
git add src/fetcher.py tests/test_fetcher_cache_isolation.py
git commit -m "feat: refactor fetcher caching to save raw JSON under league path"
```

---

### Task 4: 實作 SettingsHandler 與 SetLeagueIdHandler

**Files:**
- Modify: `src/handlers/settings_handler.py`
- Create: `src/handlers/set_league_id_handler.py`
- Create: `tests/handlers/test_settings_and_setup.py`
- Modify: `bot.py` (註冊新 Handler)

- [ ] **Step 1: 撰寫設置與設定聯盟 ID 流程的單元測試**

在 `tests/handlers/test_settings_and_setup.py` 中寫入以下測試：
```python
import pytest
from unittest.mock import MagicMock, patch
from src.handlers.settings_handler import SettingsHandler
from src.handlers.set_league_id_handler import SetLeagueIdHandler

def test_settings_handler_shows_flex_menu():
    handler = SettingsHandler()
    handler.reply_flex = MagicMock()
    
    event = MagicMock()
    config = MagicMock()
    
    # 測試 A: 當 LEAGUE_ID 未設定時，回傳僅含「設置聯盟ID」的選單
    with patch("src.handlers.settings_handler.load_config", return_value={"LEAGUE_ID": None}):
        handler.execute(event, config)
        handler.reply_flex.assert_called_once()
        args, kwargs = handler.reply_flex.call_args
        assert "設置選單" in args[2]

def test_set_league_id_handler_success():
    handler = SetLeagueIdHandler()
    handler.reply_text = MagicMock()
    
    event = MagicMock()
    event.message.text = "#設置聯盟ID 12345"
    config = MagicMock()
    
    with patch("src.handlers.set_league_id_handler.sync_season_metadata") as mock_sync, \
         patch("builtins.open", pytest.mock_open()) as mock_file:
        handler.execute(event, config)
        
        mock_sync.assert_called_once()
        handler.reply_text.assert_called_once_with(
            event, 
            config, 
            "✅ 聯盟 ID 設置成功，並已完成賽季資訊同步！"
        )
```

- [ ] **Step 2: 執行測試並確認其失敗**

Run: `.venv\Scripts\python -m pytest tests/handlers/test_settings_and_setup.py -v`
Expected: FAIL (ModuleNotFoundError 或 AttributeError)

- [ ] **Step 3: 修改 SettingsHandler 輸出選單**

修改 `src/handlers/settings_handler.py`，動態建構 Flex 選單：
```python
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from src.handlers.base_handler import BaseHandler
from src.config import load_config
from src.visualizer.flex_builder import build_button_menu_card

class SettingsHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.requires_whitelist = True
        
    def can_handle(self, user_text: str) -> bool:
        return user_text.strip() == "#設置"
        
    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        config = load_config()
        league_id = config.get("LEAGUE_ID")
        
        if not league_id:
            title = "⚙️ 系統初始化設置"
            subtitle = "目前尚未配置聯盟 ID，請先完成設置："
            buttons = [("設置聯盟 ID", "#設置聯盟ID ")]
        else:
            title = f"⚙️ 聯盟設置 (ID: {league_id})"
            subtitle = "可調整的選單項目："
            # 依要求，除了設置聯盟ID（目前叫更換聯盟ID）其餘全部標為 (即將推出) 且不可點擊 (不綁定指令/Action)
            # 我們傳入空指令代表 disabled/不可點擊
            buttons = [
                ("設置選秀時間 (即將推出)", ""),
                ("設置玩家暱稱 (即將推出)", ""),
                ("更換聯盟ID (即將推出)", ""),
                ("移除聯盟ID (即將推出)", "")
            ]
            
        flex_dict = build_button_menu_card(title, subtitle, buttons)
        self.reply_flex(event, configuration, "設置選單", flex_dict)

    @property
    def instruction_desc(self) -> str:
        return "#設置 : (限白名單) 顯示系統設置選單"
```

- [ ] **Step 4: 實作 SetLeagueIdHandler 類別**

建立 `src/handlers/set_league_id_handler.py`：
```python
import re
import os
import json
import logging
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from src.handlers.base_handler import BaseHandler
from src.config import load_config
from src.fetcher import YahooFantasyFetcher
from src.utils.season_utils import sync_season_metadata
from src.utils.path_utils import get_league_team_mapping_path

class SetLeagueIdHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.requires_whitelist = True
        
    def can_handle(self, user_text: str) -> bool:
        return user_text.strip().startswith("#設置聯盟ID")
        
    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = event.message.text.strip()
        match = re.match(r"^#設置聯盟ID\s+(\d+)$", user_text)
        if not match:
            self.reply_text(event, configuration, "格式錯誤，請使用：#設置聯盟ID <純數字_ID>")
            return
            
        target_id = match.group(1)
        config = load_config()
        
        # 建立 Fetcher 並嘗試同步賽季資訊以驗證 ID 效力
        fetcher = YahooFantasyFetcher(
            client_id=config.get("YAHOO_CLIENT_ID"),
            client_secret=config.get("YAHOO_CLIENT_SECRET")
        )
        
        try:
            sync_season_metadata(fetcher, target_id)
        except Exception as e:
            logging.error(f"[SetLeagueIdHandler] 驗證聯盟同步失敗 {target_id}: {e}")
            self.reply_text(event, configuration, "⚠️ 設置失敗，無法從 Yahoo 獲取該聯盟資訊，請確認 ID 是否正確。")
            return
            
        # 同步成功，寫入設定檔 data/security/league_config.json
        security_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "security"))
        os.makedirs(security_dir, exist_ok=True)
        config_path = os.path.join(security_dir, "league_config.json")
        
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({"LEAGUE_ID": target_id}, f, indent=2)
                
            # 初始化該聯賽的空對應檔
            mapping_path = get_league_team_mapping_path(target_id)
            if not os.path.exists(mapping_path):
                os.makedirs(os.path.dirname(mapping_path), exist_ok=True)
                with open(mapping_path, "w", encoding="utf-8") as mf:
                    json.dump({}, mf)
                    
            self.reply_text(event, configuration, "✅ 聯盟 ID 設置成功，並已完成賽季資訊同步！")
        except Exception as fe:
            logging.error(f"[SetLeagueIdHandler] 寫入設定檔失敗: {fe}")
            self.reply_text(event, configuration, "⚠️ 設置成功但儲存設定時發生內部錯誤。")

    @property
    def instruction_desc(self) -> str:
        return "#設置聯盟ID <ID> : (限白名單) 設置並同步指定之 Yahoo 聯盟 ID"
```

- [ ] **Step 5: 在 bot.py 中導入並註冊**

修改 `bot.py`，於頂部導入 `SetLeagueIdHandler`：
```python
from src.handlers.set_league_id_handler import SetLeagueIdHandler
```
並在 `bot.py` 的 `dispatcher` 註冊區塊加入：
```python
dispatcher.register(SetLeagueIdHandler())
```

- [ ] **Step 6: 執行測試確認通過**

Run: `.venv\Scripts\python -m pytest tests/handlers/test_settings_and_setup.py -v`
Expected: PASS

- [ ] **Step 7: 提交變更**

首先執行 git 分支檢查保護機制：
Run: `git branch --show-current`
Expected: `feat/settings-flex-menu`
若確認無誤，執行提交：
```bash
git add src/handlers/settings_handler.py src/handlers/set_league_id_handler.py tests/handlers/test_settings_and_setup.py bot.py
git commit -m "feat: implement SettingsHandler and SetLeagueIdHandler with instant API sync check"
```

---

### Task 5: 調整現有 Handler 适配與整體整合測試

**Files:**
- Modify: `src/handlers/base_handler.py`
- Modify: `src/handlers/intent_router.py`
- Modify: `src/handlers/stats_handler.py`
- Modify: `src/handlers/misc_handler.py`
- Modify: `main.py`

- [ ] **Step 1: 修正 BaseHandler 的隊伍暱稱對應表路徑**

修改 `src/handlers/base_handler.py` 中的 `_load_team_mapping`，使用 `get_league_team_mapping_path()`：
```python
    def _load_team_mapping(self) -> dict:
        """Load and return the team mapping from json config file."""
        from src.utils.path_utils import get_league_team_mapping_path
        mapping_file = get_league_team_mapping_path()
        if os.path.exists(mapping_file):
            try:
                with open(mapping_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Failed to load team mapping in BaseHandler: {e}")
        else:
            logging.warning(f"Team mapping file does not exist: {mapping_file}")
        return {}
```

- [ ] **Step 2: 修正 IntentRouter 的隊伍暱稱對應表路徑**

修改 `src/handlers/intent_router.py` 中的 `_load_team_mapping`，使用 `get_league_team_mapping_path()`：
```python
    def _load_team_mapping(self) -> dict:
        """Load and return the team mapping from json config file."""
        import os
        import json
        from src.utils.path_utils import get_league_team_mapping_path
        mapping_file = get_league_team_mapping_path()
        if os.path.exists(mapping_file):
            try:
                with open(mapping_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                import logging
                logging.error(f"Failed to load team mapping in IntentRouter: {e}")
        return {}
```

- [ ] **Step 3: 修正 StatsHandler 的圖片路徑與 lock 檔隔離路徑**

修改 `src/handlers/stats_handler.py` 中的 `execute` 成員方法。
導入 `get_league_dir` 與 `get_league_image_dir`，並變更 `img_path` 與 `lock_file` 路徑：
```python
        # Unified image cache key
        img_filename = f"{target_date}_combined.png"
        cache_key = f"{target_date}_combined"

        # The rest is the same standard cache checking/execution
        from src.utils.path_utils import get_league_dir, get_league_image_dir
        img_path = os.path.join(get_league_image_dir(), img_filename)
```
以及更新鎖定檔路徑：
```python
        lock_file = os.path.join(get_league_dir(), f"{cache_key}_fetch.lock")
```

- [ ] **Step 4: 修正 MiscHandler 的獎金圖片獲取路徑**

修改 `src/handlers/misc_handler.py` 中 `_handle_prize` 的圖片查找優先順序，優先查詢聯賽資料夾：
```python
    def _handle_prize(self, event: MessageEvent, configuration: Configuration) -> None:
        config = load_config()
        prize_image_path = config.get("PRIZE_IMAGE_PATH") or "data/images/bonus.png"
        
        from src.utils.path_utils import get_league_image_dir
        league_img_dir = get_league_image_dir()
        filename = os.path.basename(prize_image_path)
        img_path = os.path.join(league_img_dir, filename)
        
        if not os.path.exists(img_path):
            if os.path.exists(prize_image_path):
                img_path = prize_image_path
            else:
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                resolved_path = os.path.join(project_root, prize_image_path)
                if os.path.exists(resolved_path):
                    img_path = resolved_path
                else:
                    default_bonus = os.path.join(project_root, "data", "images", "bonus.png")
                    if os.path.exists(default_bonus):
                        img_path = default_bonus
                    else:
                        logging.info("Prize image path does not exist anywhere, ignoring")
                        return
                        
        server_url = config.get("SERVER_URL")
        if not server_url:
            logging.info("SERVER_URL not configured, ignoring")
            return
```

- [ ] **Step 5: 修正 main.py 圖片目錄與儲存目錄隔離**

修改 `main.py` 的 `main` 方法，動態解析並隔離所使用的儲存路徑與圖片路徑：
```python
        from src.utils.path_utils import get_league_dir, get_league_image_dir, get_league_team_mapping_path
        
        mapping_file = get_league_team_mapping_path(league_id)
        team_mapping = {}
        if os.path.exists(mapping_file):
            try:
                with open(mapping_file, "r", encoding="utf-8") as f:
                    team_mapping = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logging.warning(f"Failed to load team mapping from {mapping_file}: {e}")
                
        fetcher = YahooFantasyFetcher(
            team_mapping=team_mapping,
            client_id=config.get("YAHOO_CLIENT_ID"),
            client_secret=config.get("YAHOO_CLIENT_SECRET")
        )
        storage = JsonStorage(data_dir=get_league_dir(league_id))
```
同時，更新 visualization 中的 `image_dir`：
```python
            image_dir = get_league_image_dir(league_id)
            os.makedirs(image_dir, exist_ok=True)
```

- [ ] **Step 6: 執行全系統單元測試確保沒有 Regression**

Run: `.venv\Scripts\python -m pytest`
Expected: 所有 190+ 個單元測試均成功通過。

- [ ] **Step 7: 提交變更**

首先執行 git 分支檢查保護機制：
Run: `git branch --show-current`
Expected: `feat/settings-flex-menu`
若確認無誤，執行提交：
```bash
git add src/handlers/base_handler.py src/handlers/intent_router.py src/handlers/stats_handler.py src/handlers/misc_handler.py main.py
git commit -m "refactor: redirect all metadata, mappings, and image storage under isolation league path"
```
