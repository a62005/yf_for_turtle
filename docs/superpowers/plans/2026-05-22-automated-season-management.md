# 自動化賽季管理與日期驗證 (Automated Season Lifecycle) 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 自動化獲取賽季起迄日期，實作本地快取，並在 `bot.py` 中建立智慧日期驗證邏輯。

**Architecture:** 
1. `src/fetcher.py` 負責向 Yahoo API 請求聯盟元數據。
2. `src/cache_utils.py` 負責將元數據持久化至 `data/league_metadata.json`。
3. `bot.py` 啟動時更新快取，並在訊息處理流程中根據快取日期進行多重攔截與導向。

**Tech Stack:** Python, XML Parsing (`xml.etree.ElementTree`), JSON.

---

### Task 1: 增強工具層 (Fetcher & Cache)

**Files:**
- Modify: `src/fetcher.py`
- Modify: `src/cache_utils.py`

- [ ] **Step 1: 在 src/fetcher.py 中實作 fetch_league_metadata**

新增函式以獲取 `start_date`, `end_date`, `is_finished` 等欄位。

```python
    def fetch_league_metadata(self, league_id: str) -> dict:
        league_id = self._normalize_league_id(league_id)
        url = f"league/{league_id}"
        data = self.ctx.make_request(url)
        import xml.etree.ElementTree as ET
        root = ET.fromstring(data)
        
        league_node = self._find_node(root, 'ns:league')
        if league_node is not None:
            return {
                "start_date": self._find_node(league_node, 'ns:start_date').text,
                "end_date": self._find_node(league_node, 'ns:end_date').text,
                "season": self._find_node(league_node, 'ns:season').text,
                "is_finished": self._find_node(league_node, 'ns:is_finished').text
            }
        return {}
```

- [ ] **Step 2: 在 src/cache_utils.py 中實作 Metadata 持久化**

新增載入與儲存函式。

```python
METADATA_FILE = os.path.join("data", "league_metadata.json")

def load_league_metadata():
    if not os.path.exists(METADATA_FILE):
        return None
    try:
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return None

def save_league_metadata(data):
    data["last_updated"] = datetime.now().isoformat()
    os.makedirs(os.path.dirname(METADATA_FILE), exist_ok=True)
    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
```

- [ ] **Step 3: 提交變更**

```bash
git add src/fetcher.py src/cache_utils.py
git commit -m "feat: add league metadata fetching and caching utilities"
```

---

### Task 2: 配置去中心化

**Files:**
- Modify: `src/config.py`
- Modify: `league.env`

- [ ] **Step 1: 修改 src/config.py 移除強制日期檢查**

將 `SEASON_START_DATE` 設為選填。

```python
    # 修改 load_config 中對 SEASON_START_DATE 的處理
    season_start = os.getenv("SEASON_START_DATE") # 不再提供預設值，允許為 None
```

- [ ] **Step 2: 從 league.env 移除 SEASON_START_DATE**

- [ ] **Step 3: 提交變更**

```bash
git add src/config.py league.env
git commit -m "chore: remove manual SEASON_START_DATE from config"
```

---

### Task 3: 實作 bot.py 驗證矩陣

**Files:**
- Modify: `bot.py`

- [ ] **Step 1: 實作啟動時的 Metadata 同步**

在 `if __name__ == "__main__":` 區塊加入同步邏輯，確保每次重啟都拿到最新日期。

- [ ] **Step 2: 在 handle_message 中注入日期驗證邏輯**

實作以下順序的檢查：
1. **未來攔截**: `target_date > today` -> 回覆「我不是未來人」
2. **賽季前攔截**: `target_date < start_date` -> 回覆「查無當天數據」
3. **休賽季導向**: `today > end_date` 且 `#戰績` -> 設定 `target_date = end_date` 並 Log 導向紀錄
4. **賽季後攔截**: `target_date > end_date` -> 回覆「查無當天數據」

- [ ] **Step 3: 提交變更**

```bash
git add bot.py
git commit -m "feat: implement smart date validation and off-season redirection in bot"
```

---

### Task 4: 最終驗證

- [ ] **Step 1: 執行 bot.py 並測試未來日期**
發送 `#戰績20990101`，確認回覆「我不是未來人」。

- [ ] **Step 2: 測試休賽季導向**
（假設目前為 2026-05-22）發送 `#戰績`，確認是否自動抓取 2026-04-05 的數據。

- [ ] **Step 3: 測試過往日期**
發送 `#戰績20200101`，確認回覆「查無當天數據」。
