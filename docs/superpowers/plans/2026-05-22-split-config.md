# 配置管理重構 (Split Environment Config) 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將配置拆分為公開的 `league.env` 與私密的 `.env`，提升維護效率並保護隱私。

**Architecture:** 修改 `src/config.py` 中的 `load_config`，使其優先載入 `league.env`，再以 `override=True` 載入 `.env`，實現配置分層與覆蓋機制。

**Tech Stack:** Python, `python-dotenv`.

---

### Task 1: 基礎設施與測試準備

**Files:**
- Modify: `.gitignore`
- Create: `tests/test_config_split.py`

- [ ] **Step 1: 更新 .gitignore 以允許 league.env**

確保 `league.env` 可以被 Git 追蹤。

```text
# 在 .gitignore 中確保沒有排除 league.env
# 如果有 *.env 則需加上 !league.env
```

- [ ] **Step 2: 編寫配置載入測試**

建立一個測試來驗證雙檔案載入邏輯。

```python
import os
from src.config import load_config
import pytest

def test_config_load_priority(tmp_path, monkeypatch):
    # 模擬根目錄
    d = tmp_path / "project"
    d.mkdir()
    monkeypatch.chdir(d)
    
    # 建立測試用的 env 檔案
    league_env = d / "league.env"
    league_env.write_text("LEAGUE_ID=123\nSEASON_START_DATE=2025-01-01")
    
    private_env = d / ".env"
    private_env.write_text("LEAGUE_ID=456\nYAHOO_CLIENT_ID=secret_token")
    
    # 執行載入
    config = load_config()
    
    # 驗證覆蓋與合併邏輯
    assert config["LEAGUE_ID"] == "456" # .env 應覆蓋 league.env
    assert config["SEASON_START_DATE"] == "2025-01-01" # 來自 league.env
    assert config["YAHOO_CLIENT_ID"] == "secret_token" # 來自 .env
```

- [ ] **Step 3: 執行測試並確認失敗**

Run: `pytest tests/test_config_split.py`
Expected: FAIL (因為目前 load_config 只讀取單一檔案)

---

### Task 2: 實作配置載入邏輯

**Files:**
- Modify: `src/config.py`

- [ ] **Step 1: 修改 load_config 支援多檔案載入**

```python
import os
from dotenv import load_dotenv

def load_config() -> dict:
    # 1. 載入公開的聯盟設定 (不覆蓋系統環境變數)
    load_dotenv("league.env")
    
    # 2. 載入私密設定 (override=True 以便覆蓋 league.env 中的值)
    load_dotenv(".env", override=True)
    
    league_id = os.getenv("LEAGUE_ID")
    # ... 其餘邏輯保持不變
```

- [ ] **Step 2: 執行測試驗證**

Run: `pytest tests/test_config_split.py`
Expected: PASS

- [ ] **Step 3: 提交變更**

```bash
git add src/config.py
git commit -m "feat: implement split environment config loading"
```

---

### Task 3: 建立與遷移環境檔案

**Files:**
- Create: `league.env`
- Modify: `.env`
- Modify: `.env.example`

- [ ] **Step 1: 建立 league.env**

將非隱私設定移入此檔案。

```text
LEAGUE_ID=你的實際聯盟ID
SEASON_START_DATE=2025-10-21
TEAM_MAPPING_FILE=team_mapping.json
```

- [ ] **Step 2: 清理 .env**

從 `.env` 中移除已經移至 `league.env` 的欄位（或者保留它們以作為本地覆蓋）。

- [ ] **Step 3: 更新 .env.example**

```text
# --- League Settings (Public, tracked by Git) ---
# Moved to league.env

# --- Private Settings (Secret, NOT tracked) ---
YAHOO_CLIENT_ID=...
# ...
```

- [ ] **Step 4: 提交環境檔案變更**

```bash
git add league.env .env.example
git commit -m "chore: split config into league.env and .env"
```

---

### Task 4: 最終驗證

- [ ] **Step 1: 執行 bot.py 驗證**

執行並確認是否能正常啟動（雖然 TOKEN 可能不全，但應能通過設定載入階段）。

Run: `python3 bot.py`

- [ ] **Step 2: 執行現有測試**

確保沒有破壞現有的功能。

Run: `pytest`
