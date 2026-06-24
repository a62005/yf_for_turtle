# Yahoo Fantasy NBA LINE Bot Flex 卡片重構實作計畫 (Plan)

本計畫基於設計文件 [2026-06-24-flex-card-refactoring-design.md](file:///C:/Users/HsiehLink/Python/yf_for_turtle/docs/superpowers/specs/2026-06-24-flex-card-refactoring-design.md) 制定。本計畫的目標是逐步實作 `flex_builder.py`，重構現有的 Handler，並通過單元測試確保其動態性與視覺一致性。

---

## 1. 實作步驟

### 階段一：建立卡片產生器與單元測試 (基礎建設)

#### 步驟 1.1：建立 `src/visualizer/flex_builder.py`
* 實作底層私有元件：
  * `_create_bubble`
  * `_create_header`
  * `_create_separator`
* 實作對外公開的模板函數：
  * `build_stats_list_card` (完全動態遍歷 `sections`)
  * `build_matchup_comparison_card` (完全動態遍歷 `comparison_rows`)
  * `build_status_badge_list_card` (動態處理狀態標籤)
  * `build_button_menu_card` (動態處理按鈕列表)

#### 步驟 1.2：撰寫單元測試 `tests/test_visualizer_flex_builder.py`
* 測試 `build_stats_list_card`：驗證單 section 與雙 sections 的渲染，並測試包含 9 項指標與 12 項指標的動態擴展。
* 測試 `build_matchup_comparison_card`：驗證勝負判定樣式（my_win, opp_win, tie），並測試動態項目擴展。
* 測試 `build_status_badge_list_card`：驗證有傷兵球員時的 Badge 顏色與無傷兵時的綠色提示。
* 測試 `build_button_menu_card`：驗證產出的按鈕指令。
* 執行測試以確保基礎建設正常。

---

### 階段二：Handler 重構 (逐步抽離與驗證)

#### 步驟 2.1：重構 `BaseHandler` 與 `InjuryHandler`
* 修改 [base_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/base_handler.py)，導入 `build_button_menu_card`。
* 修改 [injury_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/injury_handler.py)，導入 `build_status_badge_list_card`，並移除冗餘代碼。
* 執行 `pytest tests/test_injury_handler.py` 確保功能無 regression。

#### 步驟 2.2：重構 `PlayerHandler`
* 修改 [player_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/player_handler.py)，導入 `build_stats_list_card`。
* 移除重複的 `reply_flex` 與原生的 `format_player_stats`。
* 執行 `pytest tests/test_player_handler.py` 進行驗證。

#### 步驟 2.3：重構 `UserStatsHandler`
* 修改 [user_stats_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/user_stats_handler.py)，導入 `build_stats_list_card`（傳入雙區塊）。
* 執行 `pytest tests/test_user_stats_handler.py` 進行驗證。

#### 步驟 2.4：重構 `MatchupHandler`
* 修改 [matchup_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/matchup_handler.py)，導入 `build_matchup_comparison_card`。
* 執行 `pytest tests/test_matchup_handler.py` 進行驗證。

---

### 階段三：全面集成測試與代碼清理

* 執行 `pytest` 跑過專案中的所有測試，確保整體覆蓋率與功能完全正常。
* 清理所有 Handler 內未被使用的 import，並將結果呈報給用戶進行分支合併審查。

---

## 2. 測試與驗證指令
* 新增測試執行指令：
  `pytest tests/test_visualizer_flex_builder.py -v`
* 全域測試執行指令：
  `pytest`

---

## 3. 回滾 (Rollback) 計劃
* 若重構過程中遇到嚴重不可修復之 Bug，可使用 `git checkout .` 放棄當前修改，或直接切換回 `dev` 分支，保障主幹代碼安全性。
