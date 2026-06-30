# MLB 數據優化實作計劃

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 優化 MLB 戰績查詢與 Flex Message，將投手與野手數據區分開來（圖片生成兩張，FLEX 訊息在同個氣泡內上下區分呈現）。

**Architecture:** 
1. 於數據處理階段增加 `is_pitcher` 及 `is_common` 標記。
2. 於 `main.py` 與 `StatsHandler` 針對 MLB 分別渲染並發送投手/野手兩張戰績圖。
3. 重構 `flex_builder.py` 之 `build_stats_list_card` 與 `build_matchup_comparison_card` 排版，使其在 MLB 模式下插入分隔線與標題，實現上下分區。

**Tech Stack:** Python, pytest, linebot, jinja2

---

### Task 1: 實作 MLB 投手/野手項目判定與數據標記處理

**Files:**
- Modify: `src/visualizer/processor.py`
- Modify: `tests/test_visualizer_processor.py`

- [ ] **Step 1: 撰寫預期失敗的測試**

在 `tests/test_visualizer_processor.py` 中新增 `test_is_mlb_pitcher_stat` 與 `test_process_stats_mlb_pitcher_marking` 測試用例：

```python
from src.visualizer.processor import is_mlb_pitcher_stat, process_stats_for_visual

def test_is_mlb_pitcher_stat():
    assert is_mlb_pitcher_stat("26", "ERA") is True
    assert is_mlb_pitcher_stat("50", "IP") is True
    assert is_mlb_pitcher_stat("3", "AVG") is False
    assert is_mlb_pitcher_stat("18", "BB") is False  # 野手 BB
    assert is_mlb_pitcher_stat("39", "BB") is True   # 投手 BB

def test_process_stats_mlb_pitcher_marking():
    raw_data = {
        "team_stats": [
            {"name": "Team A", "stats": {"AVG": 0.280, "ERA": 3.50, "Today Player": 5}}
        ]
    }
    # 透過 patch mock config 與 metadata.json
    import unittest.mock as mock
    with mock.patch("src.visualizer.processor.load_config") as mock_config, \
         mock.patch("os.path.exists", return_value=True), \
         mock.patch("builtins.open", mock.mock_open(read_data='{"stat_categories": [{"stat_id": "3", "display_name": "AVG", "sort_order": 1}, {"stat_id": "26", "display_name": "ERA", "sort_order": 0}]}')):
        mock_config.return_value = {"LEAGUE_ID": "mlb.l.62358"}
        processed = process_stats_for_visual(raw_data)
        
    avg_col = next(c for c in processed if c['label'] == 'AVG')
    era_col = next(c for c in processed if c['label'] == 'ERA')
    today_col = next(c for c in processed if c['label'] == 'Today Player')
    
    assert avg_col.get("is_pitcher") is False
    assert era_col.get("is_pitcher") is True
    assert today_col.get("is_common") is True
```

- [ ] **Step 2: 執行測試並驗證其失敗**

Run: `pytest tests/test_visualizer_processor.py::test_is_mlb_pitcher_stat tests/test_visualizer_processor.py::test_process_stats_mlb_pitcher_marking -v`
Expected: FAIL (ImportError: cannot import name 'is_mlb_pitcher_stat')

- [ ] **Step 3: 實作 minimal code**

在 `src/visualizer/processor.py` 中新增 `is_mlb_pitcher_stat` 函數，並修改 `process_stats_for_visual` 以在 result 中標記 `is_pitcher` 與 `is_common`：

```python
# 於 src/visualizer/processor.py 開頭或適當位置新增：
def is_mlb_pitcher_stat(stat_id: str, display_name: str) -> bool:
    pitcher_ids = {
        "26", "27", "28", "29", "30", "31", "32", "37", "38", "39",
        "41", "42", "48", "50", "81", "82", "83", "89", "121", "122"
    }
    if stat_id in pitcher_ids:
        return True
    
    pitcher_names = {
        "IP", "ERA", "WHIP", "QS", "SV+H", "SV", "HLD", "K", "W", "L", 
        "CG", "SHO", "OUT", "K/9", "BB/9", "K/BB", "SV+HLD"
    }
    if display_name in pitcher_names:
        if display_name in ("BB", "H"):
            return False
        return True
    return False
```

並修改 `process_stats_for_visual`：
```python
        # 於 categories 屬性添加時（約第 41-45 行和第 74-79 行）加上 is_pitcher 與 is_common 的判定：
        # 通用欄位 (Today Player, Game Player) 標記為 is_common=True, is_pitcher=False
        # 迴圈加入 categories.append 時，為其設定 "is_pitcher" 與 "is_common" 欄位，例如：
        categories.append({
            "label": label,
            "data_key": disp_name,
            "sort_key": sort_key_name,
            "reverse": reverse_val,
            "is_pitcher": is_mlb_pitcher_stat(cat.get("stat_id", ""), disp_name),
            "is_common": False
        })
```
並在 `result.append`（最後的輸出）將此兩個標記帶入：
```python
        result.append({
            "label": cat["label"],
            "rows": rows,
            "reverse": cat["reverse"],
            "is_pitcher": cat.get("is_pitcher", False),
            "is_common": cat.get("is_common", False)
        })
```

- [ ] **Step 4: 執行測試並驗證其通過**

Run: `pytest tests/test_visualizer_processor.py -v`
Expected: PASS

- [ ] **Step 5: 提交變更**

```bash
git add src/visualizer/processor.py tests/test_visualizer_processor.py
git commit -m "feat: add MLB pitcher stat identification and tag result data"
```

---

### Task 2: 修改 `main.py` 以支援 MLB 雙圖渲染與推送發送

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main_push.py`

- [ ] **Step 1: 撰寫預期失敗的測試**

在 `tests/test_main_push.py` 中（或新增測試）模擬 `main` 在 MLB 模式下是否產生兩個 HTML 截圖以及發送兩張圖片的 LINE message：

```python
# 測試模擬 mlb.l.62358 被傳入時，split_mlb_stats 是否被呼叫，且發送的 ImageMessage 有兩張
```

- [ ] **Step 2: 執行測試並驗證其失敗**

Run: `pytest tests/test_main_push.py -v`
Expected: FAIL (因 main.py 還沒實作雙圖與雙 ImageMessage)

- [ ] **Step 3: 修改 `main.py` 實作**

在 `main.py` 中新增 `split_mlb_stats` 函數：

```python
def split_mlb_stats(processed_list):
    hitter_list = [c for c in processed_list if c.get("is_common") or not c.get("is_pitcher")]
    pitcher_list = [c for c in processed_list if c.get("is_common") or c.get("is_pitcher")]
    return hitter_list, pitcher_list
```

在 `main.py` 圖片生成段（約第 107-126 行）：
```python
            from src.utils.path_utils import parse_league_id
            sport, _ = parse_league_id(league_id)

            if sport == "mlb":
                daily_hitter, daily_pitcher = split_mlb_stats(daily_processed)
                weekly_hitter, weekly_pitcher = split_mlb_stats(weekly_processed)
                
                # Combined images
                hitter_html = render_stats_html(daily_hitter, weekly_hitter)
                hitter_path = os.path.join(image_dir, f"{today_str}_combined_hitter.png")
                capture_html_to_png(hitter_html, hitter_path)
                
                pitcher_html = render_stats_html(daily_pitcher, weekly_pitcher)
                pitcher_path = os.path.join(image_dir, f"{today_str}_combined_pitcher.png")
                capture_html_to_png(pitcher_html, pitcher_path)
                
                # Daily images
                capture_html_to_png(render_stats_html(daily_hitter), os.path.join(image_dir, f"{today_str}_daily_hitter.png"))
                capture_html_to_png(render_stats_html(daily_pitcher), os.path.join(image_dir, f"{today_str}_daily_pitcher.png"))
                
                # Weekly images
                capture_html_to_png(render_stats_html([], weekly_hitter), os.path.join(image_dir, f"week_{current_week}_weekly_hitter.png"))
                capture_html_to_png(render_stats_html([], weekly_pitcher), os.path.join(image_dir, f"week_{current_week}_weekly_pitcher.png"))
            else:
                # 原有 NBA 邏輯
                ...
```

在 `main.py` 推送通知發送段（約第 141-158 行）：
```python
                    if sport == "mlb":
                        img_filenames = [f"{today_str}_combined_hitter.png", f"{today_str}_combined_pitcher.png"]
                        img_urls = [f"{https_url}/images/mlb/{raw_id}/{f}" for f in img_filenames]
                        messages = [ImageMessage(original_content_url=url, preview_image_url=url) for url in img_urls]
                    else:
                        img_filename = f"{today_str}_combined.png"
                        img_url = f"{https_url}/images/{sport}/{raw_id}/{img_filename}"
                        messages = [ImageMessage(original_content_url=img_url, preview_image_url=img_url)]
```

- [ ] **Step 4: 執行測試並驗證其通過**

Run: `pytest tests/test_main_push.py -v`
Expected: PASS

- [ ] **Step 5: 提交變更**

```bash
git add main.py
git commit -m "feat: render hitter and pitcher images separately for MLB stats"
```

---

### Task 3: 修改 `StatsHandler` 的快取判定與 LINE 發送

**Files:**
- Modify: `src/handlers/stats_handler.py`
- Modify: `tests/handlers/test_stats_handler.py`

- [ ] **Step 1: 撰寫預期失敗的測試**

在 `tests/handlers/test_stats_handler.py` 中新增 `test_stats_handler_mlb_cache_hit` 測試用例，模擬當 MLB 圖片皆快取存在時，直接推送兩張 `ImageMessage`：

```python
def test_stats_handler_mlb_cache_hit():
    # 實作模擬當 hitter 和 pitcher 雙圖存在時，一次發送兩張 ImageMessage 的斷言
```

- [ ] **Step 2: 執行測試並驗證其失敗**

Run: `pytest tests/handlers/test_stats_handler.py::test_stats_handler_mlb_cache_hit -v`
Expected: FAIL

- [ ] **Step 3: 修改 `StatsHandler` 實作**

修改 [src/handlers/stats_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/stats_handler.py) 的 `execute` 函數中快取判定與發送部分（約第 164-175 行）：

```python
        from src.utils.path_utils import parse_league_id
        sport, raw_id = parse_league_id(config.get("LEAGUE_ID"))
        
        is_mlb = (sport == "mlb")
        cache_hit = False
        img_urls_to_send = []
        
        if is_mlb:
            hitter_name = f"{target_date}_combined_hitter.png"
            pitcher_name = f"{target_date}_combined_pitcher.png"
            h_path = os.path.join(get_league_image_dir(), hitter_name)
            p_path = os.path.join(get_league_image_dir(), pitcher_name)
            if os.path.exists(h_path) and os.path.exists(p_path):
                cache_hit = True
                SERVER_URL = os.getenv('SERVER_URL', 'http://localhost:5000')
                https_url = SERVER_URL.replace("http://", "https://")
                if not https_url.startswith("https://"):
                    https_url = f"https://{https_url.lstrip('https://')}"
                img_urls_to_send = [
                    f"{https_url}/images/mlb/{raw_id}/{hitter_name}",
                    f"{https_url}/images/mlb/{raw_id}/{pitcher_name}"
                ]
        else:
            if os.path.exists(img_path):
                cache_hit = True
                SERVER_URL = os.getenv('SERVER_URL', 'http://localhost:5000')
                https_url = SERVER_URL.replace("http://", "https://")
                if not https_url.startswith("https://"):
                    https_url = f"https://{https_url.lstrip('https://')}"
                img_url = f"{https_url}/images/{sport}/{raw_id}/{img_filename}"
                img_urls_to_send = [img_url]
                
        if cache_hit:
            logging.info(f"[CACHE] 命中圖片快取")
            messages_to_send = [ImageMessage(original_content_url=url, preview_image_url=url) for url in img_urls_to_send]
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=messages_to_send))
            return
```

- [ ] **Step 4: 執行測試並驗證其通過**

Run: `pytest tests/handlers/test_stats_handler.py -v`
Expected: PASS

- [ ] **Step 5: 提交變更**

```bash
git add src/handlers/stats_handler.py tests/handlers/test_stats_handler.py
git commit -m "feat: support MLB cache hit and return dual ImageMessages in StatsHandler"
```

---

### Task 4: 修改 `flex_builder.py` 支援 Separator 與上下分區

**Files:**
- Modify: `src/visualizer/flex_builder.py`
- Modify: `tests/test_visualizer_flex_builder.py`

- [ ] **Step 1: 撰寫預期失敗的測試**

修改 `tests/test_visualizer_flex_builder.py`，為 `build_stats_list_card`（多區段間加入 separator）與 `build_matchup_comparison_card`（支援 MLB 野手/投手對決區隔）新增測試用例。

- [ ] **Step 2: 執行測試並驗證其失敗**

Run: `pytest tests/test_visualizer_flex_builder.py -v`
Expected: FAIL

- [ ] **Step 3: 修改 `flex_builder.py` 實作**

修改 `build_stats_list_card`（約第 124-173 行）：
```python
    if sections:
        for i, sec in enumerate(sections):
            # 若不是第一個區段，在 section 渲染前先插入 separator
            if i > 0:
                body_contents.append(_create_separator())
            ...
```

重構 `build_matchup_comparison_card`。若為 MLB，傳入的 `comparison_rows` 格式可為二維列表或帶有分類標記，在此我們直接將其拆分為 `hitter_rows` 與 `pitcher_rows` 傳入，或是在 `comparison_rows` 之中以特殊的 tuple（如 `"separator"` 類型）進行分組渲染。
為了不破壞現有的 `build_matchup_comparison_card` 介面，我們可以傳入新參數 `is_mlb=False`。
```python
def build_matchup_comparison_card(title: str, subtitle: dict | str = None, comparison_rows: list = None, is_mlb: bool = False) -> dict:
    ...
    # 原本的 header 部分保留
    
    if comparison_rows:
        if is_mlb:
            # 分割野手與投手 row
            # 假設傳入 comparison_rows 中，投手項目的元組帶有標記
            # 或者是我們手動在 comparison_rows 裡頭找 is_pitcher = True 的元素
            # 這裡我們傳入的 comparison_rows 每個元素為 (metric_name, my_val, opp_val, status, is_aux, is_pitcher)
            hitter_rows = [r for r in comparison_rows if not r[5]]
            pitcher_rows = [r for r in comparison_rows if r[5]]
            
            # 渲染野手
            hitter_boxes = []
            hitter_boxes.append({
                "type": "text", "text": "⚾ 野手數據對決", "weight": "bold", "size": "sm", "color": "#111111", "margin": "md"
            })
            for row in hitter_rows:
                hitter_boxes.append(_build_comparison_row_box(row))
                
            # 渲染投手
            pitcher_boxes = []
            pitcher_boxes.append({
                "type": "text", "text": "🧢 投手數據對決", "weight": "bold", "size": "sm", "color": "#111111", "margin": "md"
            })
            for row in pitcher_rows:
                pitcher_boxes.append(_build_comparison_row_box(row))
                
            body_contents.append({
                "type": "box", "layout": "vertical", "spacing": "sm", "contents": hitter_boxes
            })
            body_contents.append(_create_separator())
            body_contents.append({
                "type": "box", "layout": "vertical", "spacing": "sm", "contents": pitcher_boxes
            })
        else:
            # NBA 邏輯保持原樣
            rows_boxes = [_build_comparison_row_box(r) for r in comparison_rows]
            body_contents.append({
                "type": "box", "layout": "vertical", "spacing": "sm", "contents": rows_boxes
            })
```
並實作輔助函數 `_build_comparison_row_box(row)`（即原第 259-318 行的邏輯）。

- [ ] **Step 4: 執行測試並驗證其通過**

Run: `pytest tests/test_visualizer_flex_builder.py -v`
Expected: PASS

- [ ] **Step 5: 提交變更**

```bash
git add src/visualizer/flex_builder.py tests/test_visualizer_flex_builder.py
git commit -m "feat: support separators and MLB pitcher/hitter vertical sectioning in Flex messages"
```

---

### Task 5: 優化 `UserStatsHandler` 玩家數據卡片資料組裝

**Files:**
- Modify: `src/handlers/user_stats_handler.py`
- Modify: `tests/test_user_stats_handler.py`

- [ ] **Step 1: 撰寫預期失敗的測試**

在 `tests/test_user_stats_handler.py` 中撰寫針對 MLB 模式下，FLEX 卡片是否拆分為 4 個區段（每日/每週 x 野手/投手）的測試斷言。

- [ ] **Step 2: 執行測試並驗證其失敗**

Run: `pytest tests/test_user_stats_handler.py -v`
Expected: FAIL

- [ ] **Step 3: 修改 `UserStatsHandler` 實作**

修改 [src/handlers/user_stats_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/user_stats_handler.py) 中的 `format_user_stats`：
```python
        # 在 format_user_stats 內部：
        is_mlb = (stat_categories is not None) and any("IP" in cat.get("display_name", "") or "ERA" in cat.get("display_name", "") for cat in stat_categories)
        
        if is_mlb:
            from src.visualizer.processor import is_mlb_pitcher_stat
            
            def build_mlb_stat_rows(stats, get_pitcher=False):
                rows = []
                for cat in stat_categories:
                    disp = cat["display_name"]
                    stat_id = cat.get("stat_id", "")
                    is_pitch = is_mlb_pitcher_stat(stat_id, disp)
                    if is_pitch == get_pitcher:
                        val = stats.get(disp)
                        rows.append((disp, fmt_val(disp, val)))
                return rows
                
            daily_hitter = build_mlb_stat_rows(daily_stats, get_pitcher=False)
            daily_pitcher = build_mlb_stat_rows(daily_stats, get_pitcher=True)
            weekly_hitter = build_mlb_stat_rows(weekly_stats, get_pitcher=False)
            weekly_pitcher = build_mlb_stat_rows(weekly_stats, get_pitcher=True)
            
            sections = [
                {"header": f"📅 {date_str} 野手數據", "rows": daily_hitter},
                {"header": f"⚾ {date_str} 投手數據", "rows": daily_pitcher},
                {"header": f"📊 W{week_str} 野手數據", "rows": weekly_hitter},
                {"header": f"🧢 W{week_str} 投手數據", "rows": weekly_pitcher}
            ]
        else:
            # nba fallback
            ...
```

- [ ] **Step 4: 執行測試並驗證其通過**

Run: `pytest tests/test_user_stats_handler.py -v`
Expected: PASS

- [ ] **Step 5: 提交變更**

```bash
git add src/handlers/user_stats_handler.py tests/test_user_stats_handler.py
git commit -m "feat: split MLB stats into 4 separate sections for UserStats Flex Card"
```

---

### Task 6: 優化 `MatchupHandler` 動態比對與對戰卡片資料組裝

**Files:**
- Modify: `src/handlers/matchup_handler.py`
- Modify: `tests/test_matchup_handler.py`

- [ ] **Step 1: 撰寫預期失敗的測試**

在 `tests/test_matchup_handler.py` 中加入對 MLB 模式對戰比對及包含 `is_pitcher` 標記的對戰數據行組裝測試。

- [ ] **Step 2: 執行測試並驗證其失敗**

Run: `pytest tests/test_matchup_handler.py -v`
Expected: FAIL

- [ ] **Step 3: 修改 `MatchupHandler` 實作**

修改 [src/handlers/matchup_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/matchup_handler.py)：
1. 改寫 `compare_stats`，將原本寫死 NBA 9-Cat 數據改為根據外部讀入的 `stat_categories` 動態比對。
2. 呼叫 `compare_stats` 時傳入 `stat_categories`（可自 `metadata.json` 取得或在 `execute` 中透過 fetcher 載入）。
3. 修改 `format_matchup_stats`，若是 MLB，組裝 `comparison_rows` 時，每個 tuple 多帶一個 `is_pitcher` 標記（如：`("ERA", val1, val2, status, False, True)`），並呼叫 `build_matchup_comparison_card` 時帶入 `is_mlb=True`。

詳細比對邏輯改造：
```python
    def compare_stats(self, my_stats: dict, opp_stats: dict, stat_categories: list = None) -> dict:
        if not stat_categories:
            # Fallback to NBA 9-cat
            cats_to_compare = [
                ("FG%", True), ("FT%", True), ("3PTM", True), ("PTS", True), 
                ("REB", True), ("AST", True), ("ST", True), ("BLK", True), ("TO", False)
            ]
            # 原有 NBA 比對邏輯
            ...
        else:
            # MLB / 動態比對邏輯
            wins, losses, ties = 0, 0, 0
            details = {}
            for cat in stat_categories:
                disp = cat["display_name"]
                is_larger_better = True if cat["sort_order"] == 1 else False
                
                my_raw = my_stats.get(disp)
                opp_raw = opp_stats.get(disp)
                
                # 特殊格式比對 (比如 H/AB 與 IP)
                # 實作安全轉 float 與大小比對
                # 如果相等為 ties += 1
                ...
                details[disp] = {
                    "status": status,
                    "my_val": my_val_str,
                    "opp_val": opp_val_str
                }
            return {"wins": wins, "losses": losses, "ties": ties, "details": details}
```

- [ ] **Step 4: 執行測試並驗證其通過**

Run: `pytest tests/test_matchup_handler.py -v`
Expected: PASS

- [ ] **Step 5: 提交變更**

```bash
git add src/handlers/matchup_handler.py tests/test_matchup_handler.py
git commit -m "feat: make MatchupHandler support dynamic category comparison and MLB dual grouping"
```
