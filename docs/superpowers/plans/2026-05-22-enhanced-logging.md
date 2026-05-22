# 增強執行流程日誌 (Enhanced Execution Logging) 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立標準化的日誌格式，詳盡追蹤從指令接收、數據抓取到圖表產生的完整流程。

**Architecture:** 在 `bot.py` 與 `main.py` 中嵌入具備特定標籤（如 `[LINE]`, `[YAHOO]`, `[VISUAL]`）的日誌，並細分 `main.py` 的數據抓取步驟。

**Tech Stack:** Python `logging` module.

---

### Task 1: 增強 bot.py 流程日誌

**Files:**
- Modify: `bot.py`

- [ ] **Step 1: 更新 handle_message 中的接收日誌**

在 `handle_message` 開始處加入收到的訊息文字。

```python
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_text = event.message.text.strip()
    logging.info(f"[LINE] 收到指令: {user_text}")
    # ...
```

- [ ] **Step 2: 更新快取檢查日誌**

在檢查圖片路徑與負向快取處加入標籤。

```python
    # 命中快取時
    logging.info(f"[CACHE] 命中圖片快取: {img_filename}")
    
    # 命中負向快取時
    logging.info(f"[CACHE] 命中負向快取 (無數據): {cache_key}")
```

- [ ] **Step 3: 更新執行鎖與子進程啟動日誌**

```python
    # 鎖檢查失敗時
    logging.warning(f"[LOCK] 任務正在執行中，跳過重複請求: {cache_key}")

    # 啟動子進程時
    logging.info(f"[TASK] 啟動背景更新任務 (main.py)，模式: {cmd_type}")
```

- [ ] **Step 4: 提交變更**

```bash
git add bot.py
git commit -m "feat: enhance bot.py logging with standardized labels"
```

---

### Task 2: 增強 main.py 數據抓取日誌

**Files:**
- Modify: `main.py`

- [x] **Step 1: 更新任務起始與配置載入日誌**

```python
def main():
    logging.info("[TASK] 開始執行數據更新任務...")
    # ...
    logging.info(f"[CONFIG] 載入聯盟設定，League ID: {league_id}")
```

- [x] **Step 2: 細分數據抓取步驟日誌**

在各個抓取階段前加入具體標籤。

```python
    # 賽季數據
    logging.info("[YAHOO] 正在抓取賽季總戰績 (Season Standings)...")
    
    # 週數據
    logging.info(f"[YAHOO] 正在抓取第 {current_week} 週週戰績 (Weekly Stats)...")
    
    # 日數據
    logging.info(f"[YAHOO] 正在抓取 {today_str} 當日戰績 (Daily Stats)...")
```

- [x] **Step 3: 更新視覺化階段日誌**

```python
    # 渲染與截圖
    logging.info("[VISUAL] 正在渲染統計 HTML 模板...")
    
    # 截圖成功後
    logging.info(f"[VISUAL] 圖片製作完成並儲存至: {combined_path}")
```

- [x] **Step 4: 提交變更**

```bash
git add main.py
git commit -m "feat: enhance main.py logging with fine-grained Yahoo fetching steps"
```

---

### Task 3: 最終驗證

- [ ] **Step 1: 啟動 bot.py 並觸發指令**

執行 `python bot.py`，並在 LINE 傳送 `#戰績`。

- [ ] **Step 2: 觀察終端機日誌流**

確認日誌是否包含以下順序與標籤：
1. `[LINE] 收到指令: #戰績`
2. `[TASK] 啟動背景更新任務...`
3. `[TASK] 開始執行數據更新任務...`
4. `[YAHOO] 正在抓取...` (賽季、週、日順序出現)
5. `[VISUAL] 圖片製作完成...`

- [ ] **Step 3: 確認完成**
