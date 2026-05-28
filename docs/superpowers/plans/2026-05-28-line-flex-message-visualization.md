# LINE Bot #球員與#玩家數據 Flex Message 視覺化升級實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將 LINE Bot 中的 `#球員` 與 `#玩家` 數據回傳功能，從原本在手機端易跑版的 Markdown 純文字格式，升級為高度對齊、不失真且精美的 LINE Flex Message 卡片（清爽現代極簡風），徹底解決手機端的跑版與 \`\`\` 顯露問題。

**Architecture:** 重構 `PlayerHandler` 與 `UserStatsHandler` 中的格式化方法，將其從回傳 `str` 修改為回傳符合 LINE Flex Message 規格的 `dict`。在 Handler 內實作統一的 `reply_flex` 方法將其解析並傳送。數據行採用 `align: "end"` 保證全螢幕與裝置完美右貼齊。

**Tech Stack:** Python, LINE Messaging API (FlexMessage, FlexContainer), Pytest, Pytest-mock

---

### Task 1: 重構 PlayerHandler 升級為單一 Flex 數據卡片

**Files:**
- Modify: [player_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/player_handler.py)
- Modify: [test_player_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/test_player_handler.py)

- [ ] **Step 1: 修改 PlayerHandler 單元測試為字典結構斷言**

修改 `tests/test_player_handler.py` 的 `test_format_stats` 方法以匹配 Flex 字典回傳值：
```python
def test_format_stats():
    handler = PlayerHandler()
    player_info = {
        "english_name": "LeBron James",
        "chinese_name": "勒布朗·詹姆斯",
        "team": "Los Angeles Lakers",
        "jersey_number": "23"
    }
    stats = {
        "stat_4": "14",
        "stat_3": "24",
        "FG%": "0.583",
        "stat_7": "3",
        "stat_6": "4",
        "FT%": "0.750",
        "3PTM": "4",
        "PTS": "35",
        "REB": "9",
        "AST": "12",
        "ST": "2",
        "BLK": "1",
        "TO": "3"
    }
    formatted = handler.format_player_stats(player_info, stats, "2026-11-12")
    
    # 斷言回傳必須是字典格式 (Flex Message)
    assert isinstance(formatted, dict)
    assert formatted["type"] == "bubble"
    
    # 驗證 Header 部分的球員英文名稱與隊伍背號
    header_box = formatted["header"]["contents"]
    assert header_box[0]["text"] == "LeBron James"
    assert header_box[1]["text"] == "Los Angeles Lakers#23"
    assert header_box[2]["text"] == "2026-11-12"
    
    # 驗證 Body 部分的數據格線對齊
    daily_stats_box = formatted["body"]["contents"][0]["contents"]
    # FGM/A 列
    assert daily_stats_box[0]["contents"][0]["text"] == "FGM/A"
    assert daily_stats_box[0]["contents"][1]["text"] == "14/24"
    assert daily_stats_box[0]["contents"][1]["align"] == "end"
    
    # PTS 列
    assert daily_stats_box[5]["contents"][0]["text"] == "PTS"
    assert daily_stats_box[5]["contents"][1]["text"] == "35"
    assert daily_stats_box[5]["contents"][1]["align"] == "end"
```

- [ ] **Step 2: 執行測試並確認其失敗**

執行：
```powershell
.venv\Scripts\python -m pytest tests/test_player_handler.py -v
```
預期結果：**FAIL** (TypeError: string indices must be integers - 因為目前仍回傳 `str` 而非 `dict`)

- [ ] **Step 3: 於 `player_handler.py` 實作 `reply_flex` 與重構 `format_player_stats`**

修改 `src/handlers/player_handler.py`：
1. 在類別開頭引入必要的 LINE 類別：
```python
# 修改 imports，在頂部引入 json
import json
from linebot.v3.messaging import ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, Configuration, FlexMessage, FlexContainer
```
2. 調整 `format_player_stats` 與新增 `reply_flex` 實作：
```python
    def reply_flex(self, event: MessageEvent, configuration: Configuration, alt_text: str, flex_dict: dict) -> None:
        flex_container = FlexContainer.from_json(json.dumps(flex_dict))
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[FlexMessage(alt_text=alt_text, contents=flex_container)]
                )
            )

    def format_player_stats(self, player_info: dict, stats: dict, date_str: str = None) -> dict:
        def to_percent_str(val):
            try:
                f_val = float(val)
                if f_val == 0.0:
                    return "-"
                return f"{f_val * 100:.1f}%"
            except (ValueError, TypeError):
                return "-"

        # FGM is stat_4, FGA is stat_3
        fgm = stats.get("stat_4", "0")
        fga = stats.get("stat_3", "0")
        fgm_a = f"{fgm}/{fga}" if fga != "0" else "0/0"
        fg_pct = to_percent_str(stats.get("FG%", "0.0"))

        # FTM is stat_7, FTA is stat_6
        ftm = stats.get("stat_7", "0")
        fta = stats.get("stat_6", "0")
        ftm_a = f"{ftm}/{fta}" if fta != "0" else "0/0"
        ft_pct = to_percent_str(stats.get("FT%", "0.0"))

        pm3 = stats.get("3PTM", "0")
        pts = stats.get("PTS", "0")
        reb = stats.get("REB", "0")
        ast = stats.get("AST", "0")
        stl = stats.get("ST", "0")
        blk = stats.get("BLK", "0")
        to = stats.get("TO", "0")

        # 構造 9-Cat 數據列 JSON 格式
        stat_rows = []
        raw_stats = [
            ("FGM/A", fgm_a), ("FG%", fg_pct), ("FTM/A", ftm_a), ("FT%", ft_pct),
            ("3PM", pm3), ("PTS", pts), ("REB", reb), ("AST", ast),
            ("STL", stl), ("BLK", blk), ("TO", to)
        ]
        for label, val in raw_stats:
            stat_rows.append({
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {"type": "text", "text": label, "color": "#666666", "size": "sm"},
                    {"type": "text", "text": val, "align": "end", "weight": "bold", "color": "#111111", "size": "sm"}
                ]
            })

        # 回傳完整的清爽極簡風 Flex dict
        return {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {"type": "text", "text": player_info.get("english_name", "Unknown"), "weight": "bold", "size": "xl", "color": "#111111"},
                    {"type": "text", "text": f"{player_info.get('team', 'Unknown')}#{player_info.get('jersey_number', '0')}", "size": "sm", "color": "#555555"},
                    {"type": "text", "text": date_str or "", "size": "xs", "color": "#888888"}
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "xs",
                        "contents": stat_rows
                    }
                ]
            }
        }
```
3. 修改 `execute` 方法中回傳傳送部分：
```python
            # 原本為：
            # reply_text = self.format_player_stats(player_info, stats_dict, target_date)
            # self.reply_text(event, configuration, reply_text)
            # 改為：
            flex_dict = self.format_player_stats(player_info, stats_dict, target_date)
            self.reply_flex(event, configuration, f"球員 {player_info.get('english_name', 'Unknown')} 數據", flex_dict)
```

- [ ] **Step 4: 重新執行測試確認其通過**

執行：
```powershell
.venv\Scripts\python -m pytest tests/test_player_handler.py -v
```
預期結果：**PASS** (5 passed)

- [ ] **Step 5: 提交變更**

執行：
```powershell
git add src/handlers/player_handler.py tests/test_player_handler.py
git commit -m "feat: refactor player stats response to LINE Flex Message with structural unit tests"
```

---

### Task 2: 重構 UserStatsHandler 升級為雙層上下對比 Flex 數據卡片

**Files:**
- Modify: [user_stats_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/user_stats_handler.py)
- Modify: [test_user_stats_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/test_user_stats_handler.py)

- [ ] **Step 1: 修改 UserStatsHandler 單元測試為字典結構斷言**

修改 `tests/test_user_stats_handler.py` 中的 `test_format_user_stats`：
```python
def test_format_user_stats():
    handler = UserStatsHandler()
    player_info = {
        "manager_name": "韋哥",
        "official_name": "Vigo's Superteam"
    }
    daily_stats = {
        "stat_4": "14", "stat_3": "24", "FG%": "0.583", "stat_7": "3", "stat_6": "4", "FT%": "0.750",
        "3PTM": "4", "PTS": "35", "REB": "9", "AST": "12", "ST": "2", "BLK": "1", "TO": "3"
    }
    weekly_stats = {
        "stat_4": "80", "stat_3": "150", "FG%": "0.533", "stat_7": "20", "stat_6": "25", "FT%": "0.800",
        "3PTM": "18", "PTS": "210", "REB": "55", "AST": "62", "ST": "12", "BLK": "8", "TO": "15"
    }
    
    formatted = handler.format_user_stats(player_info, daily_stats, weekly_stats, "2026-05-28", "24")
    
    # 斷言回傳必須是字典格式 (Flex Message Bubble)
    assert isinstance(formatted, dict)
    assert formatted["type"] == "bubble"
    
    # 驗證 Header 部分的玩家暱稱與官方名稱
    header_box = formatted["header"]["contents"]
    assert header_box[0]["text"] == "韋哥"
    assert header_box[1]["text"] == "Vigo's Superteam"
    assert header_box[2]["text"] == "2026-05-28"
    
    # 驗證 Body 部分的雙層對比格線 (當日 + 分割線 + 當週標頭 + 當週)
    body_contents = formatted["body"]["contents"]
    
    # 1. 當日數據
    daily_box = body_contents[0]["contents"]
    assert daily_box[0]["contents"][0]["text"] == "FGM/A"
    assert daily_box[0]["contents"][1]["text"] == "14/24"
    assert daily_box[5]["contents"][0]["text"] == "PTS"
    assert daily_box[5]["contents"][1]["text"] == "35"
    
    # 2. 分割線
    assert body_contents[1]["type"] == "separator"
    
    # 3. 當週標頭
    assert body_contents[2]["text"] == "W24"
    
    # 4. 當週數據
    weekly_box = body_contents[3]["contents"]
    assert weekly_box[0]["contents"][0]["text"] == "FGM/A"
    assert weekly_box[0]["contents"][1]["text"] == "80/150"
    assert weekly_box[5]["contents"][0]["text"] == "PTS"
    assert weekly_box[5]["contents"][1]["text"] == "210"
```

- [ ] **Step 2: 執行測試並確認其失敗**

執行：
```powershell
.venv\Scripts\python -m pytest tests/test_user_stats_handler.py -v
```
預期結果：**FAIL** (TypeError: string indices must be integers)

- [ ] **Step 3: 於 `user_stats_handler.py` 實作 `reply_flex` 與重構 `format_user_stats`**

修改 `src/handlers/user_stats_handler.py`：
1. 引入必要的 LINE 類別：
```python
# 修改 imports，引入 json、FlexMessage、FlexContainer
import json
from linebot.v3.messaging import ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, Configuration, FlexMessage, FlexContainer
```
2. 調整 `format_user_stats` 與新增 `reply_flex` 實作：
```python
    def reply_flex(self, event: MessageEvent, configuration: Configuration, alt_text: str, flex_dict: dict) -> None:
        flex_container = FlexContainer.from_json(json.dumps(flex_dict))
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[FlexMessage(alt_text=alt_text, contents=flex_container)]
                )
            )

    def format_user_stats(self, player_info: dict, daily_stats: dict, weekly_stats: dict, date_str: str, week_str: str) -> dict:
        def to_percent_str(val):
            try:
                f_val = float(val)
                if f_val == 0.0:
                    return "-"
                return f"{f_val * 100:.1f}%"
            except (ValueError, TypeError):
                return "-"

        def build_stat_rows(stats):
            fgm = stats.get("stat_4", "0")
            fga = stats.get("stat_3", "0")
            fgm_a = f"{fgm}/{fga}" if fga != "0" else "0/0"
            fg_pct = to_percent_str(stats.get("FG%", "0.0"))

            ftm = stats.get("stat_7", "0")
            fta = stats.get("stat_6", "0")
            ftm_a = f"{ftm}/{fta}" if fta != "0" else "0/0"
            ft_pct = to_percent_str(stats.get("FT%", "0.0"))

            pm3 = stats.get("3PTM", "0")
            pts = stats.get("PTS", "0")
            reb = stats.get("REB", "0")
            ast = stats.get("AST", "0")
            stl = stats.get("ST", "0")
            blk = stats.get("BLK", "0")
            to = stats.get("TO", "0")

            raw_stats = [
                ("FGM/A", fgm_a), ("FG%", fg_pct), ("FTM/A", ftm_a), ("FT%", ft_pct),
                ("3PM", pm3), ("PTS", pts), ("REB", reb), ("AST", ast),
                ("STL", stl), ("BLK", blk), ("TO", to)
            ]
            rows = []
            for label, val in raw_stats:
                rows.append({
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": label, "color": "#666666", "size": "sm"},
                        {"type": "text", "text": val, "align": "end", "weight": "bold", "color": "#111111", "size": "sm"}
                    ]
                })
            return rows

        daily_rows = build_stat_rows(daily_stats)
        weekly_rows = build_stat_rows(weekly_stats)

        # 組裝白底極簡雙層卡片字典
        return {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {"type": "text", "text": player_info["manager_name"], "weight": "bold", "size": "xl", "color": "#111111"},
                    {"type": "text", "text": player_info["official_name"], "size": "sm", "color": "#555555"},
                    {"type": "text", "text": date_str, "size": "xs", "color": "#888888"}
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    # 1. 當日數據
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "xs",
                        "contents": daily_rows
                    },
                    # 2. 精緻分隔線
                    {
                        "type": "separator",
                        "color": "#EAEAEA"
                    },
                    # 3. 當週週數標頭
                    {
                        "type": "text",
                        "text": f"W{week_str}",
                        "weight": "bold",
                        "size": "md",
                        "color": "#111111",
                        "margin": "md"
                    },
                    # 4. 當週數據
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "xs",
                        "contents": weekly_rows
                    }
                ]
            }
        }
```
3. 修改 `execute` 中的發送代碼：
```python
            # 原本為：
            # reply_text = self.format_user_stats(player_info, res_daily["stats"], res_weekly["stats"], target_date, str(target_week))
            # self.reply_text(event, configuration, reply_text)
            # 改為：
            flex_dict = self.format_user_stats(player_info, res_daily["stats"], res_weekly["stats"], target_date, str(target_week))
            self.reply_flex(event, configuration, f"玩家 {nickname} 數據統計", flex_dict)
```

- [ ] **Step 4: 重新執行測試確認其通過**

執行：
```powershell
.venv\Scripts\python -m pytest tests/test_user_stats_handler.py -v
```
預期結果：**PASS** (2 passed)

- [ ] **Step 5: 提交變更**

執行：
```powershell
git add src/handlers/user_stats_handler.py tests/test_user_stats_handler.py
git commit -m "feat: refactor user stats response to dual-layer LINE Flex Message with structural unit tests"
```

---

### Task 3: 執行全專案整合與安全驗證

**Files:**
- None (僅做全局整合測試)

- [ ] **Step 1: 執行全體 85 個單元測試案例**

執行：
```powershell
python -m pytest
```
預期結果：**PASS (85 passed)**，且無任何與 Flex Message 格式有關的 Warning 或 Error。

---
