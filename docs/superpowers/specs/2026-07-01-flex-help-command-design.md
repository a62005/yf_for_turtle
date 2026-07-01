# LINE Flex Message 幫助功能設計文件 (Design Spec)

本文件定義了將 Yahoo Fantasy NBA LINE 機器人的 `#幫助`（與 `#help` 等）指令，從現有的純文字回覆轉換為動態、具權限感知（Privilege-aware）的 LINE Flex Message 輪播卡片（Carousel）的設計與實作細節。

---

## 1. 需求背景與目標
現有的 `#幫助` 指令會讀取 `data/help.txt` 並直接以純文字回覆聯賽小助手的所有指令清單。為了提升使用者體驗，本案將其實作為 LINE Flex Message，以功能分類的卡片型式進行呈現，讓使用者可以透過點擊按鈕來快速發送指令。

此外，為了避免一般玩家看到管理員專屬的後台設置指令造成混淆或越權，本功能將整合權限控管系統，動態過濾卡片：
- **一般玩家**：僅能看見「戰績查詢」、「玩家與對戰」、「聯賽資訊」三張卡片。
- **白名單管理員**：額外看見第四張「管理員專區」卡片。

---

## 2. 介面視覺與佈局設計 (UI Layout)
為與目前 Bot 現有的「玩家列表」、「設定選單」保持風格一致，本 Flex Message 採用**亮色極簡 (Light Clean) 主題**：
* **背景與框架**：採用 LINE 預設的亮白色 Bubble 背景。
* **Header 標題**：採用粗體、字體大小 `xl` 的深色文字 (`#111111`)，搭配副標題 (`#555555`)。
* **按鈕設計**：全部採用 LINE 官方預設的 `secondary` 樣式，高度為 `sm`（灰色背景、黑色文字、圓角），與 `flex_builder.py` 之 `build_button_menu_card` 的按鈕樣式相同。

以下為四個 Bubble 卡片的欄位細節：

### 卡片 1: 🏆 聯賽戰績板 (card_1_stats.json)
* **主標題 (Title)**：`🏆 聯賽戰績板`
* **副標題 (Subtitle)**：`查詢最新排名與歷史戰績`
* **說明文字 (Description)**：`支援輸入 #戰績W3 或特定日期`
* **按鈕清單**：
  1. `今日戰績` (文字動作：`#戰績`)
  2. `昨日戰績` (文字動作：`#戰績昨天`)
  3. `上週戰績` (文字動作：`#戰績上週`)

### 卡片 2: ⚔️ 玩家與對戰 (card_2_players.json)
* **主標題 (Title)**：`⚔️ 玩家與對戰`
* **副標題 (Subtitle)**：`查詢本週即時比分與玩家數據`
* **說明文字 (Description)**：
  ```text
  ※ 球員數據請直接在對話框輸入：
  #球員 球員名字 (例：#球員 老詹)
  ```
* **按鈕清單**：
  1. `即時對決` (文字動作：`#對戰`)
  2. `玩家數據` (文字動作：`#玩家`)

### 卡片 3: 🏀 聯賽資訊 (card_3_info.json)
* **主標題 (Title)**：`🏀 聯賽資訊`
* **副標題 (Subtitle)**：`掌握賽季日程與聯賽資訊`
* **說明文字 (Description)**：`選秀與開季倒數僅於休賽季啟用`
* **按鈕清單**：
  1. `聯賽獎金` (文字動作：`#獎金`)
  2. `開季倒數` (文字動作：`#開季`)
  3. `選秀倒數` (文字動作：`#選秀`)

### 卡片 4: ⚙️ 管理員專區 (card_4_admin.json) - 限白名單顯示
* **主標題 (Title)**：`⚙️ 管理員專區`
* **副標題 (Subtitle)**：`聯盟後台與參數配置`
* **說明文字 (Description)**：`限聯賽白名單管理員使用`
* **按鈕清單**：
  1. `系統設置` (文字動作：`#設置`)
  2. `設置暱稱` (文字動作：`#設置玩家暱稱`)

---

## 3. 程式架構與載入邏輯

### 3.1 檔案存放規劃
在專案根目錄下新建 `data/help_flex/` 資料夾，並寫入以下 JSON 檔：
```text
C:\Users\HsiehLink\Python\yf_for_turtle
└── data
    └── help_flex
        ├── card_1_stats.json
        ├── card_2_players.json
        ├── card_3_info.json
        └── card_4_admin.json
```

### 3.2 `MiscHandler` 修改
在 `src/handlers/misc_handler.py` 中更新 `_handle_help` 的實作：

1. **獲取發送者與權限**：
   - 提取 `user_id = event.source.user_id if event.source and hasattr(event.source, 'user_id') else None`。
   - 判斷 `is_admin = security_manager.is_whitelisted(user_id)`。
2. **建構 JSON 卡片檔案路徑列表**：
   - 預設卡片：`card_1_stats.json`、`card_2_players.json`、`card_3_info.json`。
   - 若 `is_admin` 為 `True`：將 `card_4_admin.json` 追加至列表中。
3. **讀取 JSON 內容**：
   - 依序讀取檔案，並使用 `json.loads` 解析為 dict 物件，存入 `bubbles` 列表中。
4. **回覆 Flex Carousel**：
   - 將 `bubbles` 包裝成 `{"type": "carousel", "contents": bubbles}`。
   - 呼叫基底類別的 `self.reply_flex(event, configuration, alt_text="聯賽數據助手-幫助選單", flex_dict=carousel_dict)` 回覆給使用者。

---

## 4. 容錯與 Fallback 設計
為確保不論外部檔案狀態如何，幫助指令都能正常運作，本功能將實作**程式內建 Flex Message 預設值**：

1. 在 `MiscHandler` 類別中定義常數 `DEFAULT_HELP_FLEX`（包含前 3 張卡片的 Python dict 表示）。
2. 在讀取實體 JSON 檔案時，外層使用 `try...except Exception as e` 包裹：
   - 若發生 `FileNotFoundError`、`json.JSONDecodeError` 或任何未預期錯誤，程式將會輸出 error log，並**立即使回覆內容退回使用 `DEFAULT_HELP_FLEX`**。
3. 若連基底 `reply_flex` 呼叫也失敗，則做為最終防線，使用純文字的預設內容 `DEFAULT_HELP_TEXT` 發送。

---

## 5. 測試計畫 (Testing Plan)
為確保此功能正確且不影響其他功能，我們將執行以下測試案例（可於 `tests/handlers/test_misc_handler.py` 中實作）：

1. **`test_execute_help_regular_user`**：
   - Mock 白名單檢查為 `False`。
   - 觸發 `#幫助` 後，驗證 `reply_flex` 被呼叫，且收到的 Carousel contents 列表長度為 **3**，不包含管理員卡片。
2. **`test_execute_help_admin_user`**：
   - Mock 白名單檢查為 `True`。
   - 觸發 `#幫助` 後，驗證 `reply_flex` 被呼叫，且收到的 Carousel contents 列表長度為 **4**，包含管理員卡片。
3. **`test_execute_help_missing_json_fallback`**：
   - 模擬 `data/help_flex/` 目錄不存在或為空。
   - 觸發 `#幫助` 後，驗證系統成功捕獲異常，並順利發送內建常數 `DEFAULT_HELP_FLEX`，內容長度為 3。

---

## 6. 自自我審查與確認 (Spec Self-Review)
- **佔位符掃描 (Placeholder Scan)**：無任何 TODO、TBD 或未定事項。
- **一致性檢查 (Internal Consistency)**：UI 卡片名稱與實體 JSON 檔名及測試案例一致。
- **範圍檢查 (Scope Check)**：本案僅更新 `#幫助` 指令之 Flex Message 化及相關測試，範疇明確。
- **歧義檢查 (Ambiguity Check)**：明確指出一般用戶只能看到 3 張卡片，管理員才能看到 4 張。
