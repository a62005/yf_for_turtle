# 全聯盟模擬比分 (`#比分`) 功能規格書 (All-Play Score Simulation Spec)

**Status:** `ready-for-agent`  
**Date:** 2026-11-23  
**Branch:** `feat/web-ai-agent-scraper`

---

## Problem Statement

在 Yahoo Fantasy 聯賽中，原有的 `#對戰`（**即時對戰 / Scheduled Matchup**）指令僅能查看玩家與該週賽程表所配對之單一對手的各項數據與比分。然而，玩家經常需要評估自己某週的真實戰力在全聯盟處於什麼水準（例如：「小謝第 5 週會輸給哪些人？」、「如果第 2、3、4 週對上其他人會是幾比幾？」）。目前系統缺乏一個能夠將單一玩家在當週或特定歷史週次的累積數據，與聯盟內所有其他玩家逐一進行比項對決並彙整勝負比數的查詢功能。

## Solution

新增 `#比分` 指令（**全聯盟模擬比分 / All-Play Score Simulation**），由獨立的 `LocalScoreHandler` 處理：
1. 支援查詢指定玩家在**當週即時週數據 (Current Week Live Data)** 或**歷史週結算數據 (Historical Week Final Data)**（支援 `W<週數>` 與 `上週`）中，對上聯盟所有其他玩家的總比數（如 `4 : 5`、`5 : 3 : 1`）。
2. 若輸入 `#比分`（或 `#比分 W3`、`#比分 上週`）未指定玩家名稱，則自動彈出全聯盟玩家按鈕選單，點擊後直接觸發對應玩家與週次的 `#比分` 查詢。
3. 以 LINE Flex Message 卡片呈現結果：頂部標示 `WEEK {week} ALL-PLAY`、玩家暱稱與官方隊名；下方依 `🟢 勝場 (N)`、`⚪ 平手 (N)`、`🔴 敗場 (N)` 分組並按淨勝項數排序（人數為 0 的分組自動隱藏），且為該週實際配對對手加上 `⚔️ <對手> [當週對手]` 標記。
4. 同步整合至 `#幫助` 選單中的「⚔️ 玩家與對戰」卡片以及 LLM 語意路由器（`IntentRouter`），讓使用者無論透過選單點擊、標準指令或自然語言提問（如「小謝第五週會輸給哪些人」）都能觸發此功能。

## User Stories

1. As a 聯賽玩家, I want to 輸入 `#比分` 叫出所有玩家的快速選擇選單, so that 我不需要手動打字輸入玩家暱稱就能查詢全聯盟模擬比分。
2. As a 聯賽玩家, I want to 輸入 `#比分 W3` 或 `#比分 上週` 叫出帶有指定週次參數的玩家選擇選單, so that 點擊玩家按鈕時能直接查詢該玩家在該歷史週次的全聯盟模擬比分。
3. As a 聯賽玩家, I want to 輸入 `#比分 <玩家名稱>` 查詢該玩家當週最新的全聯盟模擬比分, so that 我能即時掌握該玩家目前在全聯盟的戰力分布與會輸給哪些人。
4. As a 聯賽玩家, I want to 輸入 `#比分 <玩家名稱> W<週數>`（或 `#比分W<週數> <玩家名稱>`、`#比分 W<週數> <玩家名稱>`、`#比分 <玩家名稱>W<週數>`）查詢特定週次的全聯盟模擬比分, so that 我能回顧當季任一週（如 W1~W5）該玩家對上所有人的結算比數。
5. As a 聯賽玩家, I want to 輸入 `#比分 <玩家名稱> 上週`（或 `#比分上週 <玩家名稱>`）查詢上一週的全聯盟模擬比分, so that 我能快速檢視剛結束那一週的全聯盟對決結果而不必先去查上週是第幾週。
6. As a 聯賽玩家, I want to 在查詢當週（無論是不帶週數，或明確輸入 `W<當前週數>`）時讀取當下最新的本地週數據, so that 當週還在進行中時我看到的是最新累積的即時比分。
7. As a 聯賽玩家, I want to 在查詢已結束的歷史週次時讀取該週最後一天（結算日）的本地週數據, so that 歷史週數的模擬比數能準確反映該週最終結算成績。
8. As a 聯賽玩家, I want to 在 Flex Message 卡片上看到對手依 `🟢 勝場 (N)`、`⚪ 平手 (N)`、`🔴 敗場 (N)` 分組呈現, so that 我能一眼看出該週會贏誰、和誰平手、以及會輸給哪些人。
9. As a 聯賽玩家, I want to 在某個勝負分組（例如平手、勝場或敗場）人數為 0 時自動隱藏該分組區塊, so that 卡片版面乾淨緊湊、不會出現空白無意義的分組標題。
10. As a 聯賽玩家, I want to 在每個分組內看到對手依照淨勝項數 `(wins - losses)` 由高到低排序（惜敗排在慘敗前、大勝排在小勝前）, so that 我能清楚看出與各對手的實力差距梯度。
11. As a 聯賽玩家, I want to 在卡片上看到無平手比項時顯示 `W : L`（如 `4 : 5`）、有平手比項時顯示 `W : L : T`（如 `5 : 3 : 1`）, so that 比數呈現直覺且完全符合 Fantasy 聯賽慣例。
12. As a 聯賽玩家, I want to 在對手列表中看到該週實際賽程配對的對手標有 `⚔️ <對手> [當週對手]`, so that 我能在全聯盟模擬清單中同時辨識出該週真正交手的死敵。
13. As a 聯賽玩家, I want to 在不同賽制聯盟（如 NBA 9-cat、NBA 11-cat 含 A/T 與 DD、MLB 投打比項）查詢 `#比分` 時自動套用該聯盟的比項規則與輔助項過濾（如 `FGM/A`、`FTM/A` 不計入勝負）, so that 模擬比數與 `#對戰` 及 Yahoo 官方計算 100% 一致。
14. As a 聯賽玩家, I want to 在查詢不存在或未開打的歷史週次（如 `#比分 小謝 W99` 或本地無該週檔案）時系統保持靜默不回應, so that 群組不會被錯誤提示訊息洗版（與 `#戰績W<n>` 行為一致）。
15. As a 聯賽玩家, I want to 在 `#幫助` 選單的「⚔️ 玩家與對戰」卡片上看到「全聯盟比分 (`#比分`)」按鈕與提示文字, so that 群組成員能透過幫助選單直接探索並點擊使用這項新功能。
16. As a 聯賽玩家, I want to 在單聊或群組 `@bot` 用自然語言詢問（例如：「告訴我第5週小謝會輸給哪些人」、「小謝W2對全部人的比分」、「肥儒上週跟大家比會贏誰」）時自動路由至 `#比分 <玩家> [W<週數>|上週]`, so that 不記指令語法也能透過 AI 助手直接獲得全聯盟模擬比分卡片。

## Implementation Decisions

- **新增獨立處理器 `LocalScoreHandler`**：
  - 繼承 `BaseHandler` 並註冊於 `CommandDispatcher`。
  - 支援指令解析：識別 `#比分` 前綴，並從參數中解析選填的週次標記（`W<數字>` 或 `上週`，不分大小寫、支援在玩家名稱前或後、支援有無空白間隔）與選填的玩家名稱（匹配 `team_mapping.json` 的自訂暱稱，或本地週數據中的 `name` / `official_name`）。
  - 當未提供玩家名稱時（如 `#比分`、`#比分 W3`、`#比分 上週`），回覆按鈕選單卡片（標題 `📊 全聯盟比分查詢`，按鈕指令依是否有週次參數自動組裝為 `#比分 <玩家>` 或 `#比分 <玩家> W3`）。
- **週次資料定位與當週/歷史週讀取規則**：
  - 複用當季邊界與週次解析邏輯（對齊 `StatsHandler` 與 `LocalMatchupHandler`）：
    - **未指定週次**，或**指定的 `W<n>` 等於當前週次**：讀取當週當下最新的本地 `weekly` JSON 數據（優先依據切日規則讀取當日對應之 `date_<YYYY-MM-DD>_weekly.json`，若尚未產生則退回該當週最新一天的本地 `weekly` JSON）。若本地完全無任何當週數據，回覆 `"查無當週對戰數據"`。
    - **指定 `上週` 或歷史 `W<n>`**：掃描本地當季所有 `weekly` JSON 檔案並解析各檔案所屬週次，選取屬於目標週次中**日期最新（即該週最後一天結算）**的 `weekly` JSON 檔案。若目標週次小於 1、超出當季範圍、或本地找不到該週次的任何 `weekly` JSON 檔案，則**靜默忽略不回應**。
- **比項計算與對手排序邏輯**：
  - 直接複用 `LocalMatchupHandler.compare_stats(my_stats, opp_stats, stat_categories)` 進行一對一比項對決，確保 9-cat、11-cat（含 `A/T`、`DD` 等自訂比項）及 MLB 比項的勝負平判定與 `#對戰` 完全一致。
  - 利用 `LocalMatchupHandler._build_matchups_from_weekly_data(weekly_data, team_mapping)` 找出查詢玩家在該週的實際配對對手 `team_id`，標記 `is_actual_opponent = True`。
  - 將聯盟內除查詢玩家外的所有其他隊伍分為三組：
    - **勝場 (`wins > losses`)**
    - **平手 (`wins == losses`)**
    - **敗場 (`wins < losses`)**
  - 每組內部排序鍵：`(-(wins - losses), -wins, losses, not is_actual_opponent, original_index)`，即淨勝項數由高到低、勝項數由高到低、同分時當週實際對手優先。
- **Flex Message 視覺組裝 (`build_all_play_score_card`)**：
  - 於視覺化建構模組新增 `build_all_play_score_card(title, player_info, win_rows, tie_rows, loss_rows)`：
    - 頂部顯示 `WEEK {week} ALL-PLAY`（置中灰字 `xxs`）、玩家暱稱（粗體 `xl`）與官方隊名（灰字 `xs`），**不顯示**全聯盟模擬總戰績灰底框。
    - 依序渲染 `🟢 勝場 ({len})`、`⚪ 平手 ({len})`、`🔴 敗場 ({len})` 三個區塊；若該區塊列表為空（長度為 0），則**完全不渲染該區塊與其前置分隔線**。
    - 每一列左方顯示對手暱稱（若 `is_actual_opponent` 為真，顯示 `⚔️ <對手暱稱>` 與淺藍底 `當週對手` 徽章），右方靠右對齊顯示比數（`ties > 0` 時為 `{wins} : {losses} : {ties}`，否則為 `{wins} : {losses}`）。
- **`#幫助` 選單與 LLM 語意路由更新**：
  - 更新「⚔️ 玩家與對戰」幫助卡片與 `MiscHandler` 內建 Fallback 及過濾邏輯：在按鈕區加入 `全聯盟比分`（發送 `#比分`），並更新說明文字支援 `#對戰 [暱稱]`、`#比分 [暱稱]`、`#玩家 [暱稱]`。
  - 更新 `SYSTEM_PROMPT`（於 `intent_router_prompt.py`）與 `LocalScoreHandler.instruction_desc`：明確定義當使用者詢問某玩家在某週（或本週、上週、W1~Wn）「會輸給哪些人」、「會贏誰」、「跟全聯盟所有人比的比數/模擬比分」時，轉換為 `#比分 <玩家名稱>`、`#比分 <玩家名稱> W<週數>` 或 `#比分 <玩家名稱> 上週`。

## Testing Decisions

- **测试接縫 (Testing Seams)**：
  - 我們完全沿用專案現有的最高層級 Handler 與 Dispatcher 接縫：
    1. **Handler 執行與指令判定接縫**：透過 `LocalScoreHandler.can_handle(text)` 與 `LocalScoreHandler.execute(mock_event, mock_config)` 進行測試，輸入模擬的 LINE `MessageEvent` 並攔截 `reply_flex` / `reply_text`，直接驗證輸出的 Flex Message JSON 結構、分組隱藏、比數字串與靜默行為（不測內部私有函式細節）。
    2. **Dispatcher / IntentRouter / MiscHandler 整合接縫**：透過 `CommandDispatcher` 與 `MiscHandler` 驗證 `#幫助` 選單渲染包含 `#比分`，並透過 `IntentRouter` 驗證自然語言轉換為 `#比分` 指令並派發至 `LocalScoreHandler`。
- **沙盒規範 (Sandboxing)**：
  - 所有測試皆使用 `tmp_path` 並 mock `src.utils.path_utils.DATA_DIR`，絕不讀寫或污染正式 `data/` 資料夾。
- **Prior Art**：
  - 參照 `tests/test_local_matchup_handler.py` 與 `tests/handlers/test_stats_handler.py` 的測試模式。

## Out of Scope

- 不在 `#比分` 的 Flex Message 卡片中展開每一場模擬對決贏或輸的具體比項明細（如 `FG%`、`PTS` 等細項僅保留於 `#對戰` 一對一卡片）。
- 不在卡片頂部顯示「全聯盟模擬戰績 X勝 Y敗 Z平」的灰底匯總框。
- 不針對歷史週次啟動遠端網頁爬蟲（`WebAgentFetcher`），所有週數據皆讀取自本地 `weekly/*.json`。

## Further Notes

- 領域詞彙已同步記錄於根目錄 `GLOSSARY.md`。
