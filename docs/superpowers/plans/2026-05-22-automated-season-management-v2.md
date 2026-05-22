# 自動化賽季管理與日期驗證 (Automated Season Lifecycle) 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 自動化獲取賽季起迄日期，實作本地快取，並在 `bot.py` 中建立智慧日期驗證邏輯（攔截未來、過往日期，並導向休賽季請求）。

**Architecture:** 
- `src/fetcher.py`: 負責原始 API 通訊與 XML 解析。
- `src/cache_utils.py`: 處理 `data/league_metadata.json` 的持久化。
- `bot.py`: 在入口處同步數據，並在處理循環中注入驗證矩陣。

**Tech Stack:** Python, XML Parsing, JSON.

---

### Task 1: 增強工具層 (Fetcher & Cache)

**Files:**
- Modify: `src/fetcher.py`
- Modify: `src/cache_utils.py`
- Create: `tests/test_season_utils.py`

- [ ] **Step 1: 編寫 Fetcher 與快取測試**

```python
import os
import json
from src.cache_utils import save_league_metadata, load_league_metadata

def test_metadata_cache(tmp_path, monkeypatch):
    test_file = tmp_path / "metadata.json"
    monkeypatch.setattr("src.cache_utils.METADATA_FILE", str(test_file))
    
    data = {"start_date": "2025-10-21", "end_date": "2026-04-05"}
    save_league_metadata(data)
    
    loaded = load_league_metadata()
    assert loaded["start_date"] == "2025-10-21"
    assert "last_updated" in loaded
```

- [ ] **Step 2: 執行測試並確認失敗 (RED)**

Run: `pytest tests/test_season_utils.py`
Expected: FAIL (函式尚未定義)

- [ ] **Step 3: 實作 Metadata 獲取與快取功能 (GREEN)**

在 `src/fetcher.py` 中新增 `fetch_league_metadata`。
在 `src/cache_utils.py` 中新增 `save_league_metadata` 與 `load_league_metadata`。

- [ ] **Step 4: 驗證測試通過 (REFACTOR)**

Run: `pytest tests/test_season_utils.py`
Expected: PASS

- [ ] **Step 5: 提交變更**

```bash
git add src/fetcher.py src/cache_utils.py tests/test_season_utils.py
git commit -m "feat: implement metadata fetching and caching utilities"
```

---

### Task 2: 配置去中心化

**Files:**
- Modify: `src/config.py`
- Modify: `league.env`

- [ ] **Step 1: 修改 src/config.py 使日期變數為選填**

```python
    # src/config.py
    season_start = os.getenv("SEASON_START_DATE") # 移除 ValueError 檢查
```

- [ ] **Step 2: 移除 league.env 中的 SEASON_START_DATE**

- [ ] **Step 3: 驗證應用程式仍能啟動**

Run: `python3 -m src.config` (或執行既有測試)
Expected: 無報錯且測試通過

- [ ] **Step 4: 提交變更**

```bash
git add src/config.py league.env
git commit -m "chore: remove manual season date dependency from config"
```

---

### Task 3: 實作 bot.py 驗證矩陣

**Files:**
- Modify: `bot.py`
- Create: `tests/test_bot_dates.py`

- [ ] **Step 1: 編寫日期驗證測試**

模擬 Metadata 快取，測試 `bot.py` 中的解析邏輯（攔截、導向）。

- [ ] **Step 2: 注入啟動同步邏輯**

在 `bot.py` 啟動時：
```python
if __name__ == "__main__":
    # ... 載入 config ...
    fetcher = YahooFantasyFetcher(...)
    meta = fetcher.fetch_league_metadata(config["LEAGUE_ID"])
    save_league_metadata(meta)
```

- [ ] **Step 3: 實作智慧日期攔截與導向**

在 `handle_message` 中：
1. `target_date > today` -> 回覆「我不是未來人」
2. `target_date < start_date` -> 回覆「查無當天數據」
3. `today > end_date` 且無特定日期 -> `target_date = end_date` (Log: `偵測為休賽季，自動導向...`)
4. `target_date > end_date` -> 回覆「查無當天數據」

- [ ] **Step 4: 執行最終驗證並提交**

```bash
git add bot.py
git commit -m "feat: implement smart date validation and off-season redirection"
```
