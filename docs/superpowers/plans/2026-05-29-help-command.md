# Help Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the `#幫助` and `#help` commands to return Traditional Chinese instructions from `data/help.txt` with a robust hardcoded fallback.

**Architecture:** Modify `MiscHandler` to read `data/help.txt` using absolute paths and `utf-8` encoding. On any read failure, fallback to a predefined local plain text constant `DEFAULT_HELP_TEXT`.

**Tech Stack:** Python, pytest, line-bot-sdk-python.

---

### File Structure

We will modify two existing files:
1. `src/handlers/misc_handler.py` - Responsible for implementing the `#幫助` and `#help` commands, reading `data/help.txt`, and holding the fallback text.
2. `tests/test_misc_handler.py` - Responsible for executing test cases ensuring both successful file loading and robust fallback behavior.

---

### Task 1: Add Failing Tests for Help Command

**Files:**
- Modify: `tests/test_misc_handler.py:157-173`

- [ ] **Step 1: Write failing tests in `tests/test_misc_handler.py`**

We will replace the existing mocked stub test `test_execute_help` with two distinct tests: `test_execute_help_success` and `test_execute_help_fallback`.

Modify `tests/test_misc_handler.py` near the end:
```python
@patch("src.handlers.misc_handler.load_league_metadata")
@patch("src.handlers.misc_handler.get_pacific_date")
@patch("src.handlers.misc_handler.load_config")
@patch("src.handlers.misc_handler.ApiClient")
@patch("src.handlers.misc_handler.MessagingApi")
def test_execute_help_success(mock_messaging_api, mock_api_client, mock_load_config, mock_get_pacific, mock_load_meta, mock_event, mock_config):
    handler = MiscHandler()
    mock_event.message.text = "#幫助"
    
    mock_load_meta.return_value = {"end_date": "2026-04-12"}
    mock_get_pacific.return_value = "2026-05-29"
    
    # Mock builtins.open to return custom help content successfully
    import builtins
    mock_open = mock_open_helper = MagicMock()
    mock_open_helper.return_value.__enter__.return_value.read.return_value = "Custom Help Document"
    
    with patch("builtins.open", mock_open_helper):
        handler.execute(mock_event, mock_config)
        
        reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
        assert reply_req.reply_token == "dummy_reply_token"
        assert reply_req.messages[0].text == "Custom Help Document"


@patch("src.handlers.misc_handler.load_league_metadata")
@patch("src.handlers.misc_handler.get_pacific_date")
@patch("src.handlers.misc_handler.load_config")
@patch("src.handlers.misc_handler.ApiClient")
@patch("src.handlers.misc_handler.MessagingApi")
def test_execute_help_fallback(mock_messaging_api, mock_api_client, mock_load_config, mock_get_pacific, mock_load_meta, mock_event, mock_config):
    handler = MiscHandler()
    mock_event.message.text = "#help"
    
    mock_load_meta.return_value = {"end_date": "2026-04-12"}
    mock_get_pacific.return_value = "2026-05-29"
    
    # Mock builtins.open to raise FileNotFoundError to simulate missing file
    with patch("builtins.open", side_effect=FileNotFoundError("help.txt not found")):
        handler.execute(mock_event, mock_config)
        
        reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
        assert reply_req.reply_token == "dummy_reply_token"
        assert "歡迎使用聯賽數據助手" in reply_req.messages[0].text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `$env:PYTHONPATH="C:\Users\HsiehLink\Python\yf_for_turtle"; .venv\Scripts\pytest tests/test_misc_handler.py -v`
Expected: FAIL on `test_execute_help_success` and `test_execute_help_fallback` (because `_handle_help` is currently a no-op that doesn't send replies).

- [ ] **Step 3: Commit the failing tests**

Run:
```bash
git add tests/test_misc_handler.py
git commit -m "test: add success and fallback tests for help command"
```

---

### Task 2: Implement Help File Reading and Fallback Logic

**Files:**
- Modify: `src/handlers/misc_handler.py:138-140`

- [ ] **Step 1: Write implementation for `_handle_help`**

We will define `DEFAULT_HELP_TEXT` inside `MiscHandler` and implement the absolute path resolving, `utf-8` file reading, and exception safe fallback.

Modify `src/handlers/misc_handler.py` around line 138:
```python
    def _handle_help(self, event: MessageEvent, configuration: Configuration) -> None:
        default_help = (
            "👋 您好！歡迎使用聯賽數據助手。\n\n"
            "【常用指令】\n"
            "● #戰績 ：查詢當日聯賽綜合戰績\n"
            "● #對戰 肥儒 ：查詢指定玩家當週即時 9-Cat 對決\n"
            "● #玩家 肥儒 ：查詢指定玩家今日累積數據與排名\n"
            "● #球員 老詹 ：查詢指定球員今日即時比賽表現\n\n"
            "※ 提示：輸入「#幫助」可獲取完整的指令複製清單。"
        )
        
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        help_file_path = os.path.join(project_root, "data", "help.txt")
        
        reply_content = default_help
        try:
            if os.path.exists(help_file_path):
                with open(help_file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        reply_content = content
            else:
                logging.warning(f"Help file not found at {help_file_path}, using fallback.")
        except Exception as e:
            logging.error(f"Failed to read help file at {help_file_path}: {e}, using fallback.")
            
        self.reply_text(event, configuration, reply_content)
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `$env:PYTHONPATH="C:\Users\HsiehLink\Python\yf_for_turtle"; .venv\Scripts\pytest tests/test_misc_handler.py -v`
Expected: PASS all tests.

- [ ] **Step 3: Run the full test suite**

Run: `$env:PYTHONPATH="C:\Users\HsiehLink\Python\yf_for_turtle"; .venv\Scripts\pytest -v`
Expected: PASS all 109 tests.

- [ ] **Step 4: Commit the implementation**

Run:
```bash
git add src/handlers/misc_handler.py
git commit -m "feat: implement help command with dynamic file reading and fallback"
```
