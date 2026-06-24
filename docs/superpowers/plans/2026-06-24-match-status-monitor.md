# Yahoo Fantasy NBA - 智慧即時比賽狀態監控實作計畫 (Match Status Monitor Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將戰績查詢的「靜態時間限制阻擋」升級為利用 ESPN Scoreboard API 的「智慧即時比賽狀態監控」，以即時且精準地判定當日 NBA 賽事狀態（未開始、進行中、部分結束、全數結束），並在異常時自動退回時段備援邏輯。

**Architecture:** 
1. 在 `src/utils/time_utils.py` 中新增 `check_nba_game_status(date_str)` 負責請求與解析 ESPN Scoreboard API；
2. 修改 `is_stats_query_allowed` 整合此動態狀態檢查與原先的時段限制備援邏輯；
3. 修改 `src/handlers/stats_handler.py` 對「本日」與「當前週」戰績查詢實施此阻擋規則。

**Tech Stack:** Python 3.14+, `requests`, `pytz`, `pytest`, `pytest-mock`

---

### Task 1: 實作 ESPN API 賽事狀態檢查功能

**Files:**
- Modify: `src/utils/time_utils.py`
- Test: `tests/test_time_utils.py`

- [ ] **Step 1: 撰寫 ESPN API 檢查的單元測試**

在 `tests/test_time_utils.py` 中，使用 `unittest.mock` 模擬 `requests.get`，針對無賽事、進行中、尚未開始、跨時段未完、已結束等五種狀態撰寫測試。

```python
from unittest.mock import patch, MagicMock
import requests

def test_check_nba_game_status_empty():
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {"events": []}
        mock_get.return_value = mock_response
        
        from src.utils.time_utils import check_nba_game_status
        allowed, msg = check_nba_game_status("2026-06-24")
        assert allowed is True
        assert msg == ""

def test_check_nba_game_status_in_progress():
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "events": [
                {"status": {"type": {"state": "post"}}},
                {"status": {"type": {"state": "in"}}}
            ]
        }
        mock_get.return_value = mock_response
        
        from src.utils.time_utils import check_nba_game_status
        allowed, msg = check_nba_game_status("2026-06-24")
        assert allowed is False
        assert msg == "目前仍有比賽正在進行"

def test_check_nba_game_status_all_pre():
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "events": [
                {"status": {"type": {"state": "pre"}}},
                {"status": {"type": {"state": "pre"}}}
            ]
        }
        mock_get.return_value = mock_response
        
        from src.utils.time_utils import check_nba_game_status
        allowed, msg = check_nba_game_status("2026-06-24")
        assert allowed is False
        assert msg == "今日比賽尚未開始"

def test_check_nba_game_status_mixed_pre_post():
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "events": [
                {"status": {"type": {"state": "post"}}},
                {"status": {"type": {"state": "pre"}}}
            ]
        }
        mock_get.return_value = mock_response
        
        from src.utils.time_utils import check_nba_game_status
        allowed, msg = check_nba_game_status("2026-06-24")
        assert allowed is False
        assert msg == "今日比賽尚未全部結束，請在所有比賽結束後再進行查詢"

def test_check_nba_game_status_all_post():
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "events": [
                {"status": {"type": {"state": "post"}}},
                {"status": {"type": {"state": "post"}}}
            ]
        }
        mock_get.return_value = mock_response
        
        from src.utils.time_utils import check_nba_game_status
        allowed, msg = check_nba_game_status("2026-06-24")
        assert allowed is True
        assert msg == ""

def test_check_nba_game_status_exception():
    with patch("requests.get", side_effect=requests.RequestException("Connection error")):
        from src.utils.time_utils import check_nba_game_status
        result = check_nba_game_status("2026-06-24")
        assert result is None
```

- [ ] **Step 2: 執行測試並驗證失敗**

執行：
```powershell
$env:PYTHONPATH="."; .venv\Scripts\pytest tests/test_time_utils.py -k "test_check_nba_game_status" -v
```
預期輸出：測試因 `check_nba_game_status` 尚未實作而失敗。

- [ ] **Step 3: 實作 `check_nba_game_status` 邏輯**

在 `src/utils/time_utils.py` 開頭加入 `import requests` 與 `import logging`，並實作 `check_nba_game_status` 函數。

```python
def check_nba_game_status(date_str: str) -> tuple[bool, str] | None:
    """
    透過 ESPN Scoreboard API 即時檢查指定日期的 NBA 比賽狀態。
    參數:
        date_str: 格式為 YYYY-MM-DD 的日期字串
    回傳:
        tuple[bool, str]: (allowed, err_msg)
        None: 當 API 請求或解析發生異常時，回傳 None 以便上層進行時段降級備援。
    """
    import requests
    import logging

    try:
        espn_date = date_str.replace("-", "")
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={espn_date}"
        
        response = requests.get(url, timeout=3)
        response.raise_for_status()
        data = response.json()
        
        events = data.get("events", [])
        if not events:
            return True, ""
            
        n_pre = 0
        n_in = 0
        n_post = 0
        
        for event in events:
            status = event.get("status", {})
            status_type = status.get("type", {})
            state = status_type.get("state")  # 'pre', 'in', 'post'
            
            if state == "pre":
                n_pre += 1
            elif state == "in":
                n_in += 1
            elif state == "post":
                n_post += 1
                
        if n_in > 0:
            return False, "目前仍有比賽正在進行"
        elif n_pre > 0:
            if n_post > 0:
                return False, "今日比賽尚未全部結束，請在所有比賽結束後再進行查詢"
            else:
                return False, "今日比賽尚未開始"
        else:
            return True, ""
            
    except Exception as e:
        logging.warning(f"ESPN Scoreboard API 請求或解析失敗: {e}，將降級採用靜態時間阻擋規則。")
        return None
```

- [ ] **Step 4: 執行測試並驗證通過**

執行：
```powershell
$env:PYTHONPATH="."; .venv\Scripts\pytest tests/test_time_utils.py -k "test_check_nba_game_status" -v
```
預期輸出：所有 `test_check_nba_game_status` 單元測試通過（PASS）。

- [ ] **Step 5: 提交變更**

執行：
```powershell
git add src/utils/time_utils.py tests/test_time_utils.py
git commit -m "feat: implement check_nba_game_status using ESPN Scoreboard API"
```

---

### Task 2: 修改並整合 `is_stats_query_allowed` 決策邏輯

**Files:**
- Modify: `src/utils/time_utils.py`
- Modify: `tests/test_time_utils.py`

- [ ] **Step 1: 撰寫 `is_stats_query_allowed` 降級與整合的單元測試**

在 `tests/test_time_utils.py` 中撰寫測試，驗證當 `check_nba_game_status` 成功回傳結果時直接採用，而當其回傳 `None` 時則自動退回時段備援邏輯。

```python
def test_is_stats_query_allowed_offseason():
    from src.utils.time_utils import is_stats_query_allowed
    allowed, msg = is_stats_query_allowed(is_offseason=True)
    assert allowed is True
    assert msg == ""

def test_is_stats_query_allowed_espn_success():
    from src.utils.time_utils import is_stats_query_allowed
    # 模擬 ESPN 回傳阻擋
    with patch("src.utils.time_utils.check_nba_game_status", return_value=(False, "目前仍有比賽正在進行")):
        allowed, msg = is_stats_query_allowed(is_offseason=False, target_date="2026-06-24")
        assert allowed is False
        assert msg == "currently_in_progress_msg" # 或者 "目前仍有比賽正在進行"
        # 這裡會與 mock 傳回的值完全相同

def test_is_stats_query_allowed_fallback_blocked():
    from src.utils.time_utils import is_stats_query_allowed
    # 模擬 ESPN 失敗 (回傳 None)
    with patch("src.utils.time_utils.check_nba_game_status", return_value=None):
        # 模擬冬令時間且台北時間為早上 10 點 (尚未到 15:00)
        with patch("src.utils.time_utils.is_winter_time_pacific", return_value=True):
            mock_now = MagicMock()
            mock_now.hour = 10
            with patch("src.utils.time_utils.datetime") as mock_datetime:
                mock_datetime.now.return_value = mock_now
                mock_datetime.strptime = datetime.strptime # 保持 strptime 正常运作
                
                allowed, msg = is_stats_query_allowed(is_offseason=False, target_date="2026-06-24")
                assert allowed is False
                assert "請於 15:00 後再進行查詢。" in msg

def test_is_stats_query_allowed_fallback_allowed():
    from src.utils.time_utils import is_stats_query_allowed
    # 模擬 ESPN 失敗 (回傳 None)
    with patch("src.utils.time_utils.check_nba_game_status", return_value=None):
        # 模擬冬令時間且台北時間為下午 16 點 (已過 15:00)
        with patch("src.utils.time_utils.is_winter_time_pacific", return_value=True):
            mock_now = MagicMock()
            mock_now.hour = 16
            with patch("src.utils.time_utils.datetime") as mock_datetime:
                mock_datetime.now.return_value = mock_now
                mock_datetime.strptime = datetime.strptime
                
                allowed, msg = is_stats_query_allowed(is_offseason=False, target_date="2026-06-24")
                assert allowed is True
                assert msg == ""
```

- [ ] **Step 2: 執行測試並驗證失敗**

執行：
```powershell
$env:PYTHONPATH="."; .venv\Scripts\pytest tests/test_time_utils.py -k "test_is_stats_query_allowed" -v
```
預期輸出：部分測試失敗，因為 `is_stats_query_allowed` 尚未整合 ESPN API 且不接受 `target_date` 參數。

- [ ] **Step 3: 修改 `is_stats_query_allowed` 實作**

在 `src/utils/time_utils.py` 中修改 `is_stats_query_allowed`，使其接受 `target_date` 並整合 `check_nba_game_status`。

```python
def is_stats_query_allowed(is_offseason: bool = False, target_date: str = None) -> tuple[bool, str]:
    """
    今日綜合戰績限制在美西打完比賽後才能查詢。
    優先透過 ESPN Scoreboard API 判斷，若無法判斷則降級退回時段阻擋：
    夏令台北時間 14:00 後允許，冬令台北時間 15:00 後允許。
    """
    if is_offseason:
        return True, ""
        
    if target_date is None:
        target_date = get_target_date(is_offseason=is_offseason)
        
    # 優先嘗試外部即時狀態監控
    espn_result = check_nba_game_status(target_date)
    if espn_result is not None:
        return espn_result
        
    # API 連線或解析異常，降級退回原有的靜態時段阻擋邏輯
    allow_hour = 15 if is_winter_time_pacific() else 14
    
    tw_tz = pytz.timezone("Asia/Taipei")
    tw_hour = datetime.now(tw_tz).hour
    
    if tw_hour < allow_hour:
        return False, f"請於 {allow_hour}:00 後再進行查詢。"
    return True, ""
```

- [ ] **Step 4: 執行測試並驗證通過**

執行：
```powershell
$env:PYTHONPATH="."; .venv\Scripts\pytest tests/test_time_utils.py -k "test_is_stats_query_allowed" -v
```
預期輸出：所有 `test_is_stats_query_allowed` 相關測試通過（PASS）。

- [ ] **Step 5: 提交變更**

執行：
```powershell
git add src/utils/time_utils.py tests/test_time_utils.py
git commit -m "feat: integrate check_nba_game_status with fallback mechanism in is_stats_query_allowed"
```

---

### Task 3: 修改 `src/handlers/stats_handler.py` 套用動態監控

**Files:**
- Modify: `src/handlers/stats_handler.py:176-188`
- Test: `tests/handlers/test_stats_handler_extra.py`

- [ ] **Step 1: 撰寫 StatsHandler 對當前週查詢阻擋與放行的單元測試**

在 `tests/handlers/test_stats_handler_extra.py` 中新增兩個測試，分別模擬當前週戰績查詢（被阻擋）與歷史週戰績查詢（不被阻擋）的情境。

```python
@patch("src.handlers.stats_handler.load_config", return_value={"DEFAULT_SEASON_START": "2025-10-21"})
@patch("src.handlers.stats_handler.load_league_metadata")
@patch("src.handlers.stats_handler.get_pacific_date", return_value="2025-11-15")
@patch("src.utils.time_utils.is_stats_query_allowed", return_value=(False, "目前仍有比賽正在進行"))
@patch("src.handlers.stats_handler.ApiClient")
@patch("src.handlers.stats_handler.MessagingApi")
@patch("src.handlers.stats_handler.is_empty_data", return_value=False)
@patch("os.path.exists", return_value=False)
def test_execute_current_week_blocked(mock_exists, mock_is_empty, mock_messaging_api, mock_api_client, mock_allowed, mock_get_pacific, mock_load_meta, mock_load_config, mock_event, mock_config):
    # 當前日期 2025-11-15 應為第 4 週 (從 2025-10-21 計算)
    mock_load_meta.return_value = {"start_date": "2025-10-21", "end_date": "2026-04-05", "end_week": 23}
    
    # 用戶查詢當前週 `#戰績W4`
    mock_event.message.text = "#戰績W4"
    handler = StatsHandler()
    handler.execute(mock_event, mock_config)
    
    # 預期被阻擋，並發送錯誤提示
    reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
    assert reply_req.messages[0].text == "目前仍有比賽正在進行"

@patch("src.handlers.stats_handler.load_config", return_value={"DEFAULT_SEASON_START": "2025-10-21"})
@patch("src.handlers.stats_handler.load_league_metadata")
@patch("src.handlers.stats_handler.get_pacific_date", return_value="2025-11-15")
@patch("src.utils.time_utils.is_stats_query_allowed", return_value=(False, "目前仍有比賽正在進行"))
@patch("src.handlers.stats_handler.ApiClient")
@patch("src.handlers.stats_handler.MessagingApi")
@patch("src.handlers.stats_handler.is_empty_data", return_value=False)
@patch("os.path.exists", return_value=True) # 歷史週查詢通常會有圖片快取
def test_execute_past_week_not_blocked(mock_exists, mock_is_empty, mock_messaging_api, mock_api_client, mock_allowed, mock_get_pacific, mock_load_meta, mock_load_config, mock_event, mock_config):
    mock_load_meta.return_value = {"start_date": "2025-10-21", "end_date": "2026-04-05", "end_week": 23}
    
    # 用戶查詢歷史週 `#戰績W3` (當前是第 4 週)
    mock_event.message.text = "#戰績W3"
    handler = StatsHandler()
    handler.execute(mock_event, mock_config)
    
    # 歷史查詢不應呼叫 is_stats_query_allowed，且因為有圖片快取，正常發送圖片
    reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
    assert hasattr(reply_req.messages[0], 'original_content_url')
```

- [ ] **Step 2: 執行測試並驗證失敗**

執行：
```powershell
$env:PYTHONPATH="."; .venv\Scripts\pytest tests/handlers/test_stats_handler_extra.py -k "test_execute_current_week_blocked" -v
```
預期輸出：測試失敗，因為 `stats_handler.py` 尚未針對週數查詢 (`specific_week`) 引入 `is_stats_query_allowed` 檢查。

- [ ] **Step 3: 修改 `src/handlers/stats_handler.py` 中的攔截邏輯**

修改 `src/handlers/stats_handler.py` 中原本只檢查 `cmd_type == "combined"` 的段落，改為針對 `combined` (本日) 與當前進行中週數的 `specific_week` 查詢均執行 `is_stats_query_allowed`。

修改前：
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

修改後：
```python
        is_today_query = (cmd_type == "combined")
        current_week = date_to_week.get(today_pacific) or get_fantasy_week(start_date, today_dt)
        is_current_week_query = (cmd_type == "specific_week" and target_week == current_week)

        if is_today_query or is_current_week_query:
            from src.utils.time_utils import is_stats_query_allowed
            # 針對今日或當前週，我們皆需要檢查當日 (today_pacific) 比賽狀態來決定是否允許更新戰績
            allowed, err_msg = is_stats_query_allowed(is_offseason=is_offseason, target_date=today_pacific)
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

- [ ] **Step 4: 執行測試並驗證通過**

執行：
```powershell
$env:PYTHONPATH="."; .venv\Scripts\pytest tests/handlers/test_stats_handler_extra.py -v
```
預期輸出：所有測試（包含新增與舊有測試）皆通過（PASS）。

- [ ] **Step 5: 提交變更**

執行：
```powershell
git add src/handlers/stats_handler.py tests/handlers/test_stats_handler_extra.py
git commit -m "feat: intercept current week and today queries for match status monitor in stats handler"
```

---

### Task 4: 整體功能驗證與測試回歸

- [ ] **Step 1: 執行所有測試**

執行：
```powershell
$env:PYTHONPATH="."; .venv\Scripts\pytest
```
預期輸出：整個測試套件全部通過（PASS），無任何 Error 或 Failure。
