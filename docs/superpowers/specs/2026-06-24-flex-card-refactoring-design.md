# Yahoo Fantasy NBA LINE Bot Flex 卡片重構設計文件 (Spec)

本文件定義了將 Yahoo Fantasy NBA LINE 機器人的 Flex Message 卡片組裝邏輯，由各個 Handler 內抽離並集中實作於 `src/visualizer/flex_builder.py` 的重構規格。本設計特別針對「動態數據列增刪（例如：9-Cat 擴展至 12-Cat）」提供原生支援，不需更動任何卡片生成器程式碼。

---

## 1. 核心設計原則

1. **關注點分離 (Separation of Concerns)**：Handler 僅負責「抓取 API 資料」與「準備資料陣列」，所有的 LINE Flex JSON 結構拼接細節皆封裝在 `flex_builder.py`。
2. **高動態性 (High Dynamism)**：所有數據類型卡片均採用「動態遍歷（Dynamic Loop）」渲染。卡片不會寫死任何數據指標名稱（如 PTS、AST、FG%），行數完全隨傳入之資料長度動態調整。
3. **視覺一致性 (UI Consistency)**：所有卡片共享相同的基礎 UI 原子元件（如字型、間距、外框大小），確保回覆訊息擁有統一的精美視覺風格（白底極簡風）。

---

## 2. 新增模組設計：`flex_builder.py`

### 2.1 基礎元件 (內部私有函數)
* `_create_bubble(body_contents: list) -> dict`：包裝 Flex Bubble 最外層。
* `_create_header(title: str, subtitle: str = None) -> dict`：產生統一風格的標頭（加粗標題與灰色副標題）。
* `_create_separator(color: str = "#EAEAEA") -> dict`：精緻橫向分隔線。

### 2.2 對外公開模板 (Templates)

#### 1. 數據列表卡片 (Stats List Card)
支援球員數據與玩家當日/當週數據。**完全動態渲染行數**。
```python
def build_stats_list_card(title: str, subtitle: str = None, sections: list = None) -> dict:
    """
    sections 格式：
    [
        {
            "header": "2026-06-24",  # 區塊小標題 (可為 None)
            "rows": [
                ("FGM/A", "5/10"),
                ("FG%", "50.0%"),
                ("PTS", "25"),
                ... # 支援無限增加/減少行數
            ]
        }
    ]
    """
```
**動態實作機制**：
```python
contents = []
contents.append(_create_header(title, subtitle))

for idx, sec in enumerate(sections):
    if idx > 0:
        contents.append(_create_separator())
    
    if sec.get("header"):
        contents.append(_create_text(sec["header"], weight="bold", size="md", margin="md"))
        
    row_boxes = []
    for label, val in sec["rows"]:
        row_boxes.append({
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {"type": "text", "text": label, "color": "#666666", "size": "sm"},
                {"type": "text", "text": str(val), "align": "end", "weight": "bold", "color": "#111111", "size": "sm"}
            ]
        })
    contents.append(_create_box("vertical", row_boxes, spacing="xs"))
```

#### 2. 對戰對比卡片 (Matchup Comparison Card)
支援玩家對戰數據的左右對比。**完全動態渲染行數與勝負樣式**。
```python
def build_matchup_comparison_card(title: str, subtitle: str = None, comparison_rows: list = None) -> dict:
    """
    comparison_rows 格式：
    [
        # (指標名稱, 左側數值, 右側數值, 勝負狀態, 是否為輔助行)
        # 勝負狀態: "my_win" | "opp_win" | "tie" | None
        ("FGM/A", "25/50", "30/60", None, True),
        ("FG%", "50.0%", "50.0%", "tie", False),
        ("PTS", "110", "95", "my_win", False),
        ... # 支援無限增加/減少行數 (例如由 9 項擴增至 12 項)
    ]
    """
```
**動態實作機制**：
依據傳入的 `comparison_rows` 長度進行遍歷。對於每一行：
* 若為輔助行 (`is_aux=True`)：文字大小固定為 `sm`/`xs`，顏色為灰色。
* 若為指標比對行 (`is_aux=False`)：根據 `status` 套用動態字體與顏色（領先者大黑 `16px bold #111111`，落後者小灰 `14px regular #aaaaaa`，平手 `14px regular #555555`）。

#### 3. 傷兵名單卡片 (Status Badge List Card)
```python
def build_status_badge_list_card(title: str, subtitle: str = None, items: list = None, empty_msg: str = "🟢 目前全隊球員皆健康！") -> dict:
    """
    items 格式：
    [
        # (姓名縮寫/全名, 傷勢說明, 狀態代碼, 狀態背景顏色)
        ("S. Curry", "Knee", "O", "#922B21"),
        ...
    ]
    """
```

#### 4. 按鈕選單卡片 (Button Menu Card)
```python
def build_button_menu_card(title: str, subtitle: str = None, buttons: list = None) -> dict:
    """
    buttons 格式：
    [
        # (按鈕顯示文字, 點擊發送的訊息)
        ("陳威", "#對戰 陳威"),
        ...
    ]
    """
```

---

## 3. 各 Handler 重構與修改點

重構時，我們將進行以下異動以簡化 Handler 並消除程式碼重複：

1. **[base_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/base_handler.py)**:
   * 重構 `reply_player_list`，呼叫 `build_button_menu_card`。
2. **[injury_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/injury_handler.py)**:
   * 移除 `_build_flex_message` 與 `_get_status_color` 方法。
   * 在 `execute` 中呼叫 `build_status_badge_list_card`。
3. **[player_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/player_handler.py)**:
   * 移除重複的 `reply_flex` 方法。
   * 移除 `format_player_stats` 中的 JSON 拼接，改為呼叫 `build_stats_list_card`。
4. **[user_stats_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/user_stats_handler.py)**:
   * 移除 `format_user_stats` 的 JSON 拼接，改為呼叫 `build_stats_list_card`（包含雙 sections）。
5. **[matchup_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/matchup_handler.py)**:
   * 移除 `format_matchup_stats` 內部拼接，改為呼叫 `build_matchup_comparison_card`。

---

## 4. 測試策略與驗證
* **單元測試**：在 `tests/` 下建立 `test_visualizer_flex_builder.py`，獨立針對上述 4 個 API 的輸出 JSON 進行格式與結構斷言。
* **動態性測試**：特別撰寫測試，驗證當傳入的數據指標行數從 9 行增加至 12 行時，輸出的 Flex Message JSON 結構能正確擴展。
