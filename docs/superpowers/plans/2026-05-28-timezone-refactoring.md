# 時區與時令自動判定重構 實作計畫 (Timezone & DST Refactoring Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將系統的時間、日期跨日判定與查詢限時邏輯完全收攏至 `src/utils/time_utils.py`，支援純本地的冬/夏令時間自動判斷與 `.env` 中的 `IS_WINTER_TIME` 覆蓋設定。

**Architecture:** 
1. 實作 `src/utils/time_utils.py` 內的三個核心決策 API。
2. 重構 `PlayerHandler`、`UserStatsHandler` 和 `StatsHandler`，刪除各自的相對路徑或硬編碼時間邏輯，並對接新 API。
3. 採用 TDD 模式開發，提供完整的單元測試覆蓋。

**Tech Stack:** Python 3.14, `pytz`, `pytest`, `pytest-mock`

---

## 檔案變更結構映射 (File Structure Mapping)

* **`src/utils/time_utils.py`** [修改]：新增 `is_winter_time_pacific()`, `get_target_date()`, `is_stats_query_allowed()`。
* **`tests/test_time_utils_timezone.py`** [新增]：全面測試上述 3 個時間函數的所有邊界條件與覆蓋設定。
* **`src/handlers/player_handler.py`** [修改]：刪除舊時間邏輯，對接 `get_target_date()`。
* **`tests/test_player_handler.py`** [修改]：修正對 `get_target_date()` 的單元測試 Mock。
* **`src/handlers/user_stats_handler.py`** [修改]：刪除舊時間邏輯，對接 `get_target_date()`。
* **`tests/test_user_stats_handler.py`** [修改]：修正對 `get_target_date()` 的單元測試 Mock。
* **`src/handlers/stats_handler.py`** [修改]：刪除 `get_tw_hour`，對接 `is_stats_query_allowed()`。
* **`tests/handlers/test_stats_handler.py`** [修改]：修正戰績時間限制單元測試。

---

## 實作任務清單 (Tasks)

### Task 1: 時區與時令計算模組實作與測試 (TimeUtils TDD)

**Files:**
- Create: `tests/test_time_utils_timezone.py`
- Modify: `src/utils/time_utils.py:25-100` (接續在檔案尾端)

- [ ] **Step 1: 撰寫失敗的單元測試**
  
  建立並撰寫 `tests/test_time_utils_timezone.py`，模擬冬令與夏令的臨界時間點，確認 API 呼叫失敗。
  
  ```python
  import pytest
  from datetime import datetime
  import pytz
  from src.utils.time_utils import is_winter_time_pacific, get_target_date, is_stats_query_allowed

  def test_is_winter_time_pacific_override(mocker):
      # 測試環境變數覆蓋為冬令時
      mocker.patch("src.config.load_config", return_value={"IS_WINTER_TIME": True})
      assert is_winter_time_pacific() is True

      # 測試環境變數覆蓋為夏令時
      mocker.patch("src.config.load_config", return_value={"IS_WINTER_TIME": False})
      assert is_winter_time_pacific() is False

  def test_get_target_date_dst_boundaries(mocker):
      # 模擬為夏令時
      mocker.patch("src.utils.time_utils.is_winter_time_pacific", return_value=False)
      
      # 夏令跨日點為 7:00
      # 早上 06:59 查詢 -> 台北日期 4/5 減去 2 天 = 4/3
      dt_morning = datetime(2026, 4, 5, 6, 59, 0)
      assert get_target_date(is_offseason=False, current_tw_dt=dt_morning) == "2026-04-03"

      # 早上 07:01 查詢 -> 台北日期 4/5 減去 1 天 = 4/4
      dt_afternoon = datetime(2026, 4, 5, 7, 1, 0)
      assert get_target_date(is_offseason=False, current_tw_dt=dt_afternoon) == "2026-04-04"

  def test_get_target_date_standard_boundaries(mocker):
      # 模擬為冬令時
      mocker.patch("src.utils.time_utils.is_winter_time_pacific", return_value=True)
      
      # 冬令跨日點為 8:00
      # 早上 07:59 查詢 -> 台北日期 4/5 減去 2 天 = 4/3
      dt_morning = datetime(2026, 4, 5, 7, 59, 0)
      assert get_target_date(is_offseason=False, current_tw_dt=dt_morning) == "2026-04-03"

      # 早上 08:01 查詢 -> 台北日期 4/5 減去 1 天 = 4/4
      dt_afternoon = datetime(2026, 4, 5, 8, 1, 0)
      assert get_target_date(is_offseason=False, current_tw_dt=dt_afternoon) == "2026-04-04"

  def test_is_stats_query_allowed_dst(mocker):
      # 模擬為夏令時 (限時 14:00)
      mocker.patch("src.utils.time_utils.is_winter_time_pacific", return_value=False)
      
      # 模擬台北時間 13:59
      mock_dt = datetime(2026, 4, 5, 13, 59, 0, tzinfo=pytz.timezone("Asia/Taipei"))
      mocker.patch("src.utils.time_utils.datetime", mocker.Mock(now=lambda tz: mock_dt))
      allowed, msg = is_stats_query_allowed(is_offseason=False)
      assert allowed is False
      assert "14:00" in msg

      # 模擬台北時間 14:01
      mock_dt_ok = datetime(2026, 4, 5, 14, 1, 0, tzinfo=pytz.timezone("Asia/Taipei"))
      mocker.patch("src.utils.time_utils.datetime", mocker.Mock(now=lambda tz: mock_dt_ok))
      allowed, _ = is_stats_query_allowed(is_offseason=False)
      assert allowed is True

  def test_is_stats_query_allowed_standard(mocker):
      # 模擬為冬令時 (限時 15:00)
      mocker.patch("src.utils.time_utils.is_winter_time_pacific", return_value=True)
      
      # 模擬台北時間 14:59
      mock_dt = datetime(2026, 4, 5, 14, 59, 0, tzinfo=pytz.timezone("Asia/Taipei"))
      mocker.patch("src.utils.time_utils.datetime", mocker.Mock(now=lambda tz: mock_dt))
      allowed, msg = is_stats_query_allowed(is_offseason=False)
      assert allowed is False
      assert "15:00" in msg
  ```

- [ ] **Step 2: 執行測試並確認其失敗**
  
  執行：`$env:PYTHONPATH="." ; .venv\Scripts\pytest tests/test_time_utils_timezone.py -v`
  預期結果：FAIL (因為 API 函數尚未實作，或是發生 ImportError)

- [ ] **Step 3: 實作 minimal code**
  
  修改 `src/utils/time_utils.py`，在尾端寫入實作：
  
  ```python
  def is_winter_time_pacific() -> bool:
      """
      本地極速判斷目前美西是否為冬令時間。
      """
      from src.config import load_config
      try:
          config = load_config()
          is_winter_override = config.get("IS_WINTER_TIME")
          if is_winter_override is not None:
              if isinstance(is_winter_override, str):
                  return is_winter_override.lower() in ("true", "1", "yes")
              return bool(is_winter_override)
      except Exception:
          pass

      pacific_tz = pytz.timezone("US/Pacific")
      now_pacific = datetime.now(pacific_tz)
      is_dst = now_pacific.dst().total_seconds() != 0
      return not is_dst

  def get_target_date(is_offseason: bool = False, end_date: str = None, current_tw_dt=None) -> str:
      """
      計算並回傳目標的美西日期 YYYY-MM-DD
      """
      if is_offseason:
          return end_date or "2026-04-12"
          
      if current_tw_dt is None:
          tw_tz = pytz.timezone("Asia/Taipei")
          current_tw_dt = datetime.now(tw_tz)
          
      tw_date = current_tw_dt.date()
      tw_hour = current_tw_dt.hour
      
      cross_hour = 8 if is_winter_time_pacific() else 7
      
      if tw_hour >= cross_hour:
          target_dt = tw_date - timedelta(days=1)
      else:
          target_dt = tw_date - timedelta(days=2)
          
      return target_dt.strftime("%Y-%m-%d")

  def is_stats_query_allowed(is_offseason: bool = False) -> tuple[bool, str]:
      """
      判定今日綜合戰績 (#戰績) 查詢是否已被允許。
      """
      if is_offseason:
          return True, ""
          
      allow_hour = 15 if is_winter_time_pacific() else 14
      
      tw_tz = pytz.timezone("Asia/Taipei")
      tw_hour = datetime.now(tw_tz).hour
      
      if tw_hour < allow_hour:
          return False, f"請於 {allow_hour}:00 後再進行查詢。"
      return True, ""
  ```

- [ ] **Step 4: 重新執行測試並確認其順利通過**
  
  執行：`$env:PYTHONPATH="." ; .venv\Scripts\pytest tests/test_time_utils_timezone.py -v`
  預期結果：PASS (4 passed)

- [ ] **Step 5: Git Commit**
  
  執行：
  ```bash
  git add src/utils/time_utils.py tests/test_time_utils_timezone.py
  git commit -m "feat: implement timezone DST auto-detection and custom winter override"
  ```

---

### Task 2: 重構球員數據查詢 (PlayerHandler Integration)

**Files:**
- Modify: `src/handlers/player_handler.py:30-46` (刪除舊 calculate_target_date 函數)，及第 190-200 行 (對接新 API)
- Modify: `tests/test_player_handler.py:18-41` (修正對 `get_target_date` 呼叫的 mock 方式)

- [ ] **Step 1: 修改 PlayerHandler 程式碼**
  
  開啟並修改 `src/handlers/player_handler.py`：
  1. 移除 `class PlayerHandler` 類別內部的整個 `calculate_target_date` 函數。
  2. 在 `execute` 方法（約第 190 行）內，刪除原本呼叫 `self.calculate_target_date` 的行，改為：
     ```python
     from src.utils.time_utils import get_target_date
     target_date = get_target_date(is_offseason=is_offseason, end_date=meta.get('end_date'))
     ```

- [ ] **Step 2: 執行測試並確認其失敗**
  
  執行：`$env:PYTHONPATH="." ; .venv\Scripts\pytest tests/test_player_handler.py -v`
  預期結果：FAIL (因為舊測試還在嘗試 Mock 已經被刪除的 `calculate_target_date`)

- [ ] **Step 3: 修改 `tests/test_player_handler.py` 測試**
  
  修改 `tests/test_player_handler.py` 的 `test_calculate_target_date_regular` 與 `test_calculate_target_date_offseason` 測試。既然時間邏輯已經被移到 `time_utils`，我們可以直接呼叫 `get_target_date` 來進行測試斷言：
  
  ```python
  from src.utils.time_utils import get_target_date

  def test_calculate_target_date_regular(mocker):
      # 模擬為夏令時
      mocker.patch("src.utils.time_utils.is_winter_time_pacific", return_value=False)
      
      # 早上 6:59 查詢 -> 目標日期為 11/10
      dt_morning = datetime(2026, 11, 12, 6, 59, 0, tzinfo=pytz.timezone("Asia/Taipei"))
      target_date = get_target_date(is_offseason=False, current_tw_dt=dt_morning)
      assert target_date == "2026-11-10"

      # 早上 7:01 查詢 -> 目標日期為 11/11
      dt_afternoon = datetime(2026, 11, 12, 7, 1, 0, tzinfo=pytz.timezone("Asia/Taipei"))
      target_date = get_target_date(is_offseason=False, current_tw_dt=dt_afternoon)
      assert target_date == "2026-11-11"

  def test_calculate_target_date_offseason():
      # 休賽季 -> 強制指向設為賽季最後一天
      target_date = get_target_date(is_offseason=True, end_date="2026-04-12")
      assert target_date == "2026-04-12"
  ```

- [ ] **Step 4: 執行測試並確認其成功**
  
  執行：`$env:PYTHONPATH="." ; .venv\Scripts\pytest tests/test_player_handler.py -v`
  預期結果：PASS (5 passed)

- [ ] **Step 5: Git Commit**
  
  執行：
  ```bash
  git add src/handlers/player_handler.py tests/test_player_handler.py
  git commit -m "refactor: integrate get_target_date in PlayerHandler and clean up redundant calculations"
  ```

---

### Task 3: 重構玩家數據查詢 (UserStatsHandler Integration)

**Files:**
- Modify: `src/handlers/user_stats_handler.py:41-56` (刪除舊 calculate_target_date 函數)，及第 205-215 行 (對接新 API)
- Modify: `tests/test_user_stats_handler.py` (若有需要修正相關 Mock 斷言)

- [ ] **Step 1: 修改 UserStatsHandler 程式碼**
  
  開啟並修改 `src/handlers/user_stats_handler.py`：
  1. 移除 `class UserStatsHandler` 類別內部的整個 `calculate_target_date` 函數。
  2. 在 `execute` 方法（約第 207 行）內，刪除原本呼叫 `self.calculate_target_date` 的行，改為：
     ```python
     from src.utils.time_utils import get_target_date
     target_date = get_target_date(is_offseason=is_offseason, end_date=meta.get('end_date'))
     ```

- [ ] **Step 2: 執行測試確認無虞**
  
  執行：`$env:PYTHONPATH="." ; .venv\Scripts\pytest tests/test_user_stats_handler.py -v`
  預期結果：PASS (3 passed，因為原測試中並無對 `calculate_target_date` 進行直接 Mock)

- [ ] **Step 3: Git Commit**
  
  執行：
  ```bash
  git add src/handlers/user_stats_handler.py tests/test_user_stats_handler.py
  git commit -m "refactor: integrate get_target_date in UserStatsHandler and clean up redundant calculations"
  ```

---

### Task 4: 重構戰績查詢限制 (StatsHandler Integration)

**Files:**
- Modify: `src/handlers/stats_handler.py:19-21` (刪除 get_tw_hour 函數)，及第 170-175 行 (對接新 API)
- Modify: `tests/handlers/test_stats_handler.py` (或是 test_stats_handler 相關的測試，確保時間檢查斷言正確)

- [ ] **Step 1: 修改 StatsHandler 程式碼**
  
  開啟並修改 `src/handlers/stats_handler.py`：
  1. 移除 `get_tw_hour()` 函數定義。
  2. 在 `execute` 方法（約第 170 行）內，修改時間限制攔截邏輯：
     ```python
     is_current = cmd_type == "combined"
     if is_current:
         from src.utils.time_utils import is_stats_query_allowed
         allowed, err_msg = is_stats_query_allowed(is_offseason=is_offseason)
         if not allowed:
             with ApiClient(configuration) as api_client:
                 MessagingApi(api_client).reply_message(
                     ReplyMessageRequest(
                         reply_token=event.reply_token, 
                         messages=[TextMessage(text=err_msg)]
                     )
                 )
             return
     ```

- [ ] **Step 2: 執行測試並確認其失敗**
  
  執行：`$env:PYTHONPATH="." ; .venv\Scripts\pytest tests/handlers/test_stats_handler.py -v` (或對應測試檔案)
  預期結果：FAIL (因為舊測試還在嘗試 Mock `get_tw_hour`)

- [ ] **Step 3: 修改 `test_stats_handler.py` 測試**
  
  尋找 `tests/handlers/test_stats_handler.py` 中對 `get_tw_hour` 進行 Mock 的部分，改為 Mock `src.utils.time_utils.is_stats_query_allowed`：
  
  ```python
  def test_stats_handler_allowed_time(mocker):
      # 模擬當前時間限制為允許 (True)
      mocker.patch("src.utils.time_utils.is_stats_query_allowed", return_value=(True, ""))
      # 執行測試...
  ```
  *(註：此步驟根據實際 `test_stats_handler.py` 的內容靈活修正)*

- [ ] **Step 4: 執行測試確認通過**
  
  執行：`$env:PYTHONPATH="." ; .venv\Scripts\pytest tests/handlers/test_stats_handler.py -v` (或對應測試檔案)
  預期結果：PASS

- [ ] **Step 5: Git Commit**
  
  執行：
  ```bash
  git add src/handlers/stats_handler.py
  # 若有修改 test 檔則一併 add
  git commit -m "refactor: integrate is_stats_query_allowed in StatsHandler for robust limit verification"
  ```

---

### Task 5: 全套測試驗證與部署就緒

- [ ] **Step 1: 執行全套 pytest 測試**
  
  執行：`$env:PYTHONPATH="." ; .venv\Scripts\pytest`
  預期結果：86 個原本測試 + 新增測試 100% 全數通過 (88+ passed)

- [ ] **Step 2: 清理與提交**
  
  確保無任何殘留暫存檔案，檢查 `git status` 狀態。
  執行：
  ```bash
  git status
  ```
  確認工作區乾淨無誤，準備進行合併。
