# 設計規格書：LINE Bot #球員與#玩家數據 Flex Message 視覺化升級

本規格書詳細記錄了如何將 LINE Bot 中的 `#球員` 與 `#玩家` 數據回傳功能，從傳統的手機端易跑版 Markdown 文字，全面升級為百分之百對齊、視覺質感極高的 LINE Flex Message 卡片（清爽現代極簡風）。

---

## 1. 核心設計理念與視覺規範

1. **徹底解決跑版與 \`\`\` 顯露**：
   - 由於手機版 LINE App 不支援 Markdown 格式渲染，會直接顯露 \`\`\` 並跑版。
   - 改用 LINE Flex Message JSON 佈局，利用 CSS Flexbox 的格線佈局，確保不論在任何手機螢幕寬度與電腦版上，數據格線皆 **100% 絕對對齊**，且完全移除 \`\`\` 字元。
2. **清爽現代極簡風 (Light Mode)**：
   - **背景**：純白色背景 (`#FFFFFF`)。
   - **文字與線條**：使用墨黑色 (`#111111`) 作為加粗數據字體，中灰色 (`#555555` / `#666666`) 作為一般說明與指標名稱，淡灰色 (`#EAEAEA`) 作為分界線。
3. **排版佈局規範**：
   - **#球員 數據**：
     * 單一卡片。Header 包含球員英文名（如 `LeBron James`）、所屬球隊與背號（如 `Los Angeles Lakers#23`）、數據日期（如 `2026-05-28`）。
     * Body 為當日 9-Cat 數據表格（右側數值靠右對齊）。
   - **#玩家 數據**：
     * 單一卡片上下對比。Header 包含玩家稱呼（如 `韋哥`）、官方球隊名稱（如 `Vigo's Superteam`）、當日日期（如 `2026-05-28`）。
     * 上半部 Body 為當日數據表格。
     * 中間隔以淡灰色分界線。
     * 下半部 Body 為當週累積數據表格，帶有週數標頭（如 `W24`）。

---

## 2. 系統架構與核心組件變更

### 2.1 引入並註冊 Flex 處理方法

#### [MODIFY] [base_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/base_handler.py) 或各 Handler 本身
- 實作 `reply_flex(self, event, configuration, alt_text, flex_dict)` 方法，負責將 Python 字典經由 `FlexContainer.from_json` 轉換成 LINE `FlexMessage` 並進行回覆。

### 2.2 控制器重構

#### [MODIFY] [player_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/player_handler.py)
- 重構 `format_player_stats`：不再回傳字串，改回傳符合 LINE Flex 規範的 `dict`（白底、數據列靠右對齊）。
- 重構 `execute`：呼叫 `format_player_stats` 取得 Flex 字典，並調用 `reply_flex` 進行傳送。

#### [MODIFY] [user_stats_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/user_stats_handler.py)
- 重構 `format_user_stats`：改回傳組裝好當日與當週對比的 `dict`（雙層數據列、中間含分界線、週數標頭）。
- 重構 `execute`：調用 `reply_flex` 傳送即時 Flex 卡片。

---

## 3. Flex Message JSON 結構設計

每個數據列（Row）的橫向 Flexbox 結構概念如下：
```json
{
  "type": "box",
  "layout": "horizontal",
  "contents": [
    {
      "type": "text",
      "text": "PTS",
      "color": "#666666",
      "size": "sm"
    },
    {
      "type": "text",
      "text": "35",
      "align": "end",
      "weight": "bold",
      "color": "#111111",
      "size": "sm"
    }
  ]
}
```
利用 `align: "end"` 屬性，在任何裝置上，數值都將會筆直地向右貼齊。

---

## 4. 單元測試驗證計畫

1. **[test_player_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/test_player_handler.py)**
   - 重構 `test_format_stats`：斷言回傳的 Flex dict 欄位。例如 `formatted["body"]["contents"][0]["contents"][0]["text"] == "FGM/A"` 且對應數值正確。
2. **[test_user_stats_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/test_user_stats_handler.py)**
   - 重構 `test_format_user_stats`：驗證雙層結構中 `formatted["body"]["contents"]` 是否含有當週 W24 標頭與當週的 FGM/A 數據。
3. **驗證指令**：
   ```powershell
   python -m pytest tests/test_player_handler.py tests/test_user_stats_handler.py
   ```
