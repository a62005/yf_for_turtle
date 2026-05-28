# 設計規格書：LINE Bot #玩家與#對戰無暱稱時顯示垂直玩家選單

本設計規格書詳細規劃了如何優化 LINE Bot 中的 `#玩家` 與 `#對戰` 指令。當使用者僅輸入指令（未帶暱稱，或後面僅有空白）時，系統將動態讀取 `team_mapping.json`，並回傳一個高質感的垂直 Flex Message 按鈕選單，方便使用者直接點擊查詢。

---

## 1. 背景與目標

### 1.1 現有行為
- 目前的 `#玩家 [暱稱]` 與 `#對戰 [暱稱]` 指令要求使用者必須手動輸入完整的登記暱稱。
- 如果使用者僅輸入 `#玩家` 或 `#對戰`，系統的 `can_handle` 會直接回傳 `False` 並安靜略過，對使用者不夠友善。

### 1.2 優化目標
- 當使用者僅發送 `#玩家` 或 `#對戰`（包含後面帶有任意空白），系統應能正確識別。
- 系統將動態載入 `team_mapping.json` 的所有登記玩家，以 **「垂直單欄列表」** 的高質感 Flex Message 按鈕面板回傳。
- 每個玩家按鈕點擊後，會直接由聊天室發送對應的文字（例如 `#玩家 肥儒` 或 `#對戰 肥儒`），並自動觸發後續的數據查詢。
- 架構設計需具備高度擴充性，能相容未來人數的增加，並消除重複程式碼。

---

## 2. 詳細技術設計

### 2.1 指令正則表達式優化
我們將調整兩個 Handler 的 `self.pattern`：

*   **`UserStatsHandler`** (`src/handlers/user_stats_handler.py`):
    - 舊 Pattern: `r"^#玩家\s+(.+)$"`
    - 新 Pattern: `r"^#玩家(?:\s+(.+))?$"`
*   **`MatchupHandler`** (`src/handlers/matchup_handler.py`):
    - 舊 Pattern: `r"^#對戰\s+(.+)$"`
    - 新 Pattern: `r"^#對戰(?:\s+(.+))?$"`

### 2.2 控制流變更 (`can_handle` & `execute`)

#### 🔹 以 `UserStatsHandler` 為例的代碼邏輯
```python
def can_handle(self, user_text: str) -> bool:
    user_text = user_text.strip()
    match = self.pattern.match(user_text)
    if not match:
        return False
        
    nickname_raw = match.group(1)
    if not nickname_raw:
        # 未帶暱稱，確定可以處理（顯示玩家列表）
        return True
        
    nickname = nickname_raw.strip()
    if not nickname:
        # 去除空白後為空，亦視為未帶暱稱，可處理
        return True
        
    mapping = self._load_team_mapping()
    return nickname in mapping.values()
```

```python
def execute(self, event: MessageEvent, configuration: Configuration) -> None:
    user_text = event.message.text.strip()
    match = self.pattern.match(user_text)
    if not match:
        return
        
    nickname_raw = match.group(1)
    nickname = nickname_raw.strip() if nickname_raw else ""
    
    if not nickname:
        # 執行「顯示垂直玩家列表」
        self.reply_player_list(event, configuration, is_matchup=False)
        return
        
    # 否則執行原有「查詢單一玩家即時數據」流程
    # ...
```

---

### 2.3 消除重複：`BaseHandler` 新增共用方法
為了避免兩個 Handler 重複撰寫 Flex Message 的組裝與發送邏輯，我們將在 `BaseHandler` (`src/handlers/base_handler.py`) 中新增 `reply_player_list` 方法：

```python
def reply_player_list(self, event: MessageEvent, configuration: Configuration, is_matchup: bool) -> None:
    """動態載入玩家列表並以垂直按鈕 Flex Message 卡片回傳"""
    mapping = self._load_team_mapping() # BaseHandler 本身可載入對照表
    if not mapping:
        return
        
    # 依序取得所有玩家暱稱（去重且維持排序）
    nicknames = list(mapping.values())
    
    title = "⚔️ 對戰比分查詢" if is_matchup else "🙋‍♂️ 玩家數據查詢"
    subtitle = "請點擊下方玩家，將自動為您搜尋數據"
    command_prefix = "#對戰" if is_matchup else "#玩家"
    
    # 動態組裝垂直 Button 元件
    buttons = []
    for name in nicknames:
        buttons.append({
            "type": "button",
            "action": {
                "type": "message",
                "label": name,
                "text": f"{command_prefix} {name}"
            },
            "style": "secondary",
            "height": "sm"
        })
        
    # 組裝 Flex Message JSON 結構
    flex_dict = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "spacing": "xs",
            "contents": [
                {"type": "text", "text": title, "weight": "bold", "size": "lg", "color": "#111111"},
                {"type": "text", "text": subtitle, "size": "xs", "color": "#777777"}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": buttons
        }
    }
    
    # 透過 LINE Bot API 發送 Flex Message
    self.reply_flex(event, configuration, f"{title}選單", flex_dict)
```

> [!NOTE]
> `BaseHandler` 需要引入 `FlexContainer`、`FlexMessage` 等 LINE 相關 API 資源。

---

## 3. 測試計畫 (Test Plan)

### 3.1 單元測試擴充
我們將針對 `tests/test_user_stats_handler.py` 與 `tests/test_matchup_handler.py` 進行測試擴充。

#### 🔹 測項一：驗證 `can_handle` 匹配性
- `can_handle("#玩家")` ──► 預期 `True`
- `can_handle("#玩家  ")` ──► 預期 `True`
- `can_handle("#對戰")` ──► 預期 `True`
- `can_handle("#對戰 ")` ──► 預期 `True`
- 舊有的 `can_handle("#玩家 韋哥")` 與 `can_handle("#玩家 詹姆斯")` 行為必須不受影響。

#### 🔹 測項二：驗證 `execute` 行為
- 模擬發送僅含 `#玩家` 或 `#對戰` 的文字事件。
- 斷言系統會正確呼叫 `reply_flex`（或呼叫模擬的 API 傳送 Flex Message）。
- 驗證生成的 Flex Message 內容，確認按鈕的 `text` 分別為 `#玩家 [暱稱]` 或 `#對戰 [暱稱]`。
