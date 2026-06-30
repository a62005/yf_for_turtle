# 移除聯盟ID功能實作計畫 (Remove League ID Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 實作白名單用戶專用的「移除聯盟ID」功能，讓用戶能在對話中解除該群組綁定，且在無其他對話綁定該聯盟時自動移除該聯盟本地的所有暫存數據以釋放伺服器空間。

**Architecture:** 
1. 擴充 `SettingsHandler` 選單按鈕，將「移除聯盟ID」動作對應至 `#移除聯盟ID` 指令。
2. 擴充 `SetLeagueIdHandler`，令其 `can_handle` 額外攔截 `#移除聯盟ID` 與 `#確定移除聯盟ID`。
3. 當收到 `#移除聯盟ID`，回傳二階段確認的 Flex Message 卡片。
4. 當確認收到 `#確定移除聯盟ID`，由 `SetLeagueIdHandler` 讀取並更新 `chat_league_mapping.json`，隨後檢查是否有其他群組與此聯賽關聯。若無關聯，則使用 `shutil.rmtree` 刪除 `data/league/{sport}/{raw_id}` 資料夾，最後統一回覆解綁成功文字。

**Tech Stack:** Python 3.11, pytest, Line Messaging API SDK.

---

### Task 1: 擴充設置選單 (Modify Settings Handler)

**Files:**
- Modify: `src/handlers/settings_handler.py`
- Test: `tests/handlers/test_settings_handler.py`

- [ ] **Step 1: 寫測試案例驗證「移除聯盟ID」按鈕設定**
  
  在 `tests/handlers/test_settings_handler.py` 底下，編寫測試確認選單按鈕的動作指令由原本的空字串 `""` 改為 `"#移除聯盟ID"`。

  新增至 `tests/handlers/test_settings_handler.py`：
  ```python
  def test_settings_handler_contains_remove_league_button():
      handler = SettingsHandler()
      handler.reply_flex = MagicMock()
      event = MagicMock()
      config = MagicMock()

      with patch("src.handlers.settings_handler.load_config", return_value={"LEAGUE_ID": "12345"}), \
           patch("src.utils.cache_utils.load_league_metadata", return_value={"end_date": "2026-04-12"}), \
           patch("src.utils.time_utils.get_pacific_date", return_value="2026-04-10"):
          handler.execute(event, config)
          handler.reply_flex.assert_called_once()
          args = handler.reply_flex.call_args[0]
          flex_card = args[3]
          buttons_box = flex_card["body"]["contents"][1]
          remove_btn = [btn for btn in buttons_box["contents"] if btn["type"] == "button" and btn["action"]["label"] == "移除聯盟ID (即將推出)" or btn["action"]["label"] == "移除聯盟ID"][0]
          assert remove_btn["action"]["text"] == "#移除聯盟ID"
  ```

- [ ] **Step 2: 執行測試並驗證失敗**

  執行測試：
  `pytest tests/handlers/test_settings_handler.py::test_settings_handler_contains_remove_league_button -v`
  預期結果：失敗 (AssertionError: 動作文字為空 `""`，不等於 `"#移除聯盟ID"`)

- [ ] **Step 3: 修改 SettingsHandler 啟用按鈕與指令**

  將 [`src/handlers/settings_handler.py:44`](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/settings_handler.py#L44) 的按鈕內容從 `("移除聯盟ID (即將推出)", "")` 修改為：
  ```diff
  -                 ("移除聯盟ID (即將推出)", "")
  +                 ("移除聯盟ID", "#移除聯盟ID")
  ```

- [ ] **Step 4: 執行測試並驗證通過**

  執行測試：
  `pytest tests/handlers/test_settings_handler.py::test_settings_handler_contains_remove_league_button -v`
  預期結果：通過

- [ ] **Step 5: 提交 Commit**

  ```bash
  git add src/handlers/settings_handler.py tests/handlers/test_settings_handler.py
  git commit -m "feat(settings): enable remove league ID button action"
  ```

---

### Task 2: 實作二次確認卡片 (Implement Confirmation UI)

**Files:**
- Modify: `src/handlers/set_league_id_handler.py`
- Test: `tests/handlers/test_settings_and_setup.py`

- [ ] **Step 1: 編寫二次確認卡片的測試**

  在 `tests/handlers/test_settings_and_setup.py` 中新增 `test_set_league_id_handler_shows_remove_confirm_card` 測試：
  ```python
  def test_set_league_id_handler_shows_remove_confirm_card():
      from src.config import current_chat_id
      handler = SetLeagueIdHandler()
      handler.reply_flex = MagicMock()
      event = MagicMock()
      event.message.text = "#移除聯盟ID"
      config = MagicMock()

      token = current_chat_id.set("group_test_confirm")
      try:
          handler.execute(event, config)
          handler.reply_flex.assert_called_once()
          args = handler.reply_flex.call_args[0]
          title = args[2]
          flex_card = args[3]
          
          assert "請選擇" in title or "確認" in title
          # 檢查選單內有「確定移除」與「取消」按鈕
          buttons_box = flex_card["body"]["contents"][1]
          btn_labels = [btn["action"]["label"] for btn in buttons_box["contents"] if btn["type"] == "button"]
          assert "確定移除" in btn_labels
          assert "取消" in btn_labels
          
          confirm_btn = [btn for btn in buttons_box["contents"] if btn["type"] == "button" and btn["action"]["label"] == "確定移除"][0]
          assert confirm_btn["action"]["text"] == "#確定移除聯盟ID"
      finally:
          current_chat_id.reset(token)
  ```

- [ ] **Step 2: 執行測試並驗證失敗**

  執行測試：
  `pytest tests/handlers/test_settings_and_setup.py::test_set_league_id_handler_shows_remove_confirm_card -v`
  預期結果：失敗 (因為還沒有在 `can_handle` 與 `execute` 中實作 `#移除聯盟ID` 指令分支)

- [ ] **Step 3: 修改 SetLeagueIdHandler 攔截與回覆確認卡片**

  修改 `src/handlers/set_league_id_handler.py`：
  1. 更新 `can_handle` 判定：
     ```python
     def can_handle(self, user_text: str) -> bool:
         text = user_text.strip()
         return (
             text.startswith("#設置聯盟ID") or 
             text == "#移除聯盟ID" or 
             text == "#確定移除聯盟ID"
         )
     ```
  2. 在 `execute` 方法開頭加入處理 `#移除聯盟ID` 分支：
     ```python
         if user_text == "#移除聯盟ID":
             from src.visualizer.flex_builder import build_button_menu_card
             title = "確定要移除聯盟綁定嗎？"
             buttons = [
                 ("確定移除", "#確定移除聯盟ID"),
                 ("取消", "")
             ]
             flex_dict = build_button_menu_card(title, None, buttons)
             self.reply_flex(event, configuration, "確認移除聯盟綁定", flex_dict)
             return
     ```

- [ ] **Step 4: 執行測試驗證通過**

  執行測試：
  `pytest tests/handlers/test_settings_and_setup.py::test_set_league_id_handler_shows_remove_confirm_card -v`
  預期結果：通過

- [ ] **Step 5: 提交 Commit**

  ```bash
  git add src/handlers/set_league_id_handler.py tests/handlers/test_settings_and_setup.py
  git commit -m "feat(setup): add remove league ID confirmation dialog"
  ```

---

### Task 3: 實作解綁與孤立聯賽清理 (Implement Unbinding & Cleaning Logic)

**Files:**
- Modify: `src/handlers/set_league_id_handler.py`
- Test: `tests/handlers/test_settings_and_setup.py`

- [ ] **Step 1: 編寫解綁與刪除檔案邏輯的測試**

  在 `tests/handlers/test_settings_and_setup.py` 中，針對 `#確定移除聯盟ID` 的兩個情境（尚有其他群組綁定，以及最後一個綁定）撰寫對應測試：
  ```python
  def test_set_league_id_handler_remove_success_with_others():
      from src.config import current_chat_id
      import json
      
      handler = SetLeagueIdHandler()
      handler.reply_text = MagicMock()
      event = MagicMock()
      event.message.text = "#確定移除聯盟ID"
      config = MagicMock()
      
      written_data = {}
      def mock_mapping_io(path, mode="r", *args, **kwargs):
          import io
          class MockFile(io.StringIO):
              def __enter__(self): return self
              def __exit__(self, exc_type, exc_val, exc_tb):
                  nonlocal written_data
                  val = self.getvalue()
                  if val: written_data = json.loads(val)
              def close(self):
                  nonlocal written_data
                  val = self.getvalue()
                  if val: written_data = json.loads(val)
                  super().close()
                  
          if "chat_league_mapping.json" in str(path).replace("\\", "/"):
              if "r" in mode:
                  # 兩個群組都綁定同一聯賽 nba.l.11111
                  return MockFile('{"group_1": "nba.l.11111", "group_2": "nba.l.11111"}')
              return MockFile()
          return open(path, mode, *args, **kwargs)

      token = current_chat_id.set("group_1")
      try:
          with patch("src.handlers.set_league_id_handler.open", side_effect=mock_mapping_io), \
               patch("src.handlers.set_league_id_handler.os.path.exists", return_value=True), \
               patch("src.handlers.set_league_id_handler.get_league_dir") as mock_get_dir, \
               patch("shutil.rmtree") as mock_rmtree:
               
              handler.execute(event, config)
              
              # 驗證 mapping 中 group_1 已被移除，但 group_2 仍保留
              assert "group_1" not in written_data
              assert written_data.get("group_2") == "nba.l.11111"
              # 驗證並未執行刪除資料夾（因為還有 group_2 綁定）
              mock_rmtree.assert_not_called()
              handler.reply_text.assert_called_once_with(event, config, "✅ 已成功解除此群組的聯盟綁定。")
      finally:
          current_chat_id.reset(token)

  def test_set_league_id_handler_remove_success_and_delete_directory():
      from src.config import current_chat_id
      import json
      
      handler = SetLeagueIdHandler()
      handler.reply_text = MagicMock()
      event = MagicMock()
      event.message.text = "#確定移除聯盟ID"
      config = MagicMock()
      
      written_data = {}
      def mock_mapping_io(path, mode="r", *args, **kwargs):
          import io
          class MockFile(io.StringIO):
              def __enter__(self): return self
              def __exit__(self, exc_type, exc_val, exc_tb):
                  nonlocal written_data
                  val = self.getvalue()
                  if val: written_data = json.loads(val)
              def close(self):
                  nonlocal written_data
                  val = self.getvalue()
                  if val: written_data = json.loads(val)
                  super().close()
                  
          if "chat_league_mapping.json" in str(path).replace("\\", "/"):
              if "r" in mode:
                  # 只有 group_1 綁定 nba.l.22222
                  return MockFile('{"group_1": "nba.l.22222"}')
              return MockFile()
          return open(path, mode, *args, **kwargs)

      token = current_chat_id.set("group_1")
      try:
          with patch("src.handlers.set_league_id_handler.open", side_effect=mock_mapping_io), \
               patch("src.handlers.set_league_id_handler.os.path.exists", return_value=True), \
               patch("src.handlers.set_league_id_handler.get_league_dir", return_value="mock_dir/nba/22222"), \
               patch("shutil.rmtree") as mock_rmtree:
               
              handler.execute(event, config)
              
              # 驗證 mapping 中 group_1 被移除後已無人綁定
              assert "group_1" not in written_data
              # 驗證觸發刪除資料夾
              mock_rmtree.assert_called_once_with("mock_dir/nba/22222")
              handler.reply_text.assert_called_once_with(event, config, "✅ 已成功解除此群組的聯盟綁定。")
      finally:
          current_chat_id.reset(token)
  ```

- [ ] **Step 2: 執行測試並驗證失敗**

  執行測試：
  `pytest tests/handlers/test_settings_and_setup.py::test_set_league_id_handler_remove_success_with_others tests/handlers/test_settings_and_setup.py::test_set_league_id_handler_remove_success_and_delete_directory -v`
  預期結果：失敗 (因為還沒有 `#確定移除聯盟ID` 的實作邏輯)

- [ ] **Step 3: 實作解綁與刪除目錄邏輯**

  修改 `src/handlers/set_league_id_handler.py` 的 `execute` 方法，在 `#移除聯盟ID` 的 if 分支後方，追加處理 `#確定移除聯盟ID` 分支：
  ```python
          if user_text == "#確定移除聯盟ID":
              from src.config import current_chat_id
              from src.utils.path_utils import BASE_DIR, get_league_dir
              import shutil
              
              chat_id = current_chat_id.get() or "default"
              security_dir = os.path.join(BASE_DIR, "data", "security")
              config_path = os.path.join(security_dir, "chat_league_mapping.json")
              
              mapping = {}
              if os.path.exists(config_path):
                  try:
                      with open(config_path, "r", encoding="utf-8") as f:
                          mapping = json.load(f)
                  except Exception:
                      mapping = {}
                      
              if str(chat_id) not in mapping:
                  self.reply_text(event, configuration, "⚠️ 此群組尚未綁定任何聯盟 ID。")
                  return
                  
              # 1. 取得該群組綁定的 league_id 並解綁
              removed_league_id = mapping.pop(str(chat_id))
              
              # 寫回映射檔
              try:
                  os.makedirs(security_dir, exist_ok=True)
                  with open(config_path, "w", encoding="utf-8") as f:
                      json.dump(mapping, f, indent=2, ensure_ascii=False)
              except Exception as e:
                  logging.error(f"[SetLeagueIdHandler] 寫入映射表失敗: {e}")
                  self.reply_text(event, configuration, "⚠️ 解除綁定時寫入設定檔失敗。")
                  return
              
              # 2. 檢查是否還有其他對話框對應此 league_id
              has_others = any(str(val) == str(removed_league_id) for val in mapping.values())
              
              # 3. 若為孤立聯賽，刪除整個資料夾
              if not has_others:
                  league_dir = get_league_dir(removed_league_id)
                  if os.path.exists(league_dir):
                      try:
                          shutil.rmtree(league_dir)
                          logging.info(f"[SetLeagueIdHandler] 已成功刪除孤立聯賽目錄: {league_dir}")
                      except Exception as delete_error:
                          logging.error(f"[SetLeagueIdHandler] 刪除聯賽目錄 {league_dir} 失敗: {delete_error}")
                          
              # 4. 回覆結果
              self.reply_text(event, configuration, "✅ 已成功解除此群組的聯盟綁定。")
              return
  ```

- [ ] **Step 4: 執行測試驗證通過**

  執行測試：
  `pytest tests/handlers/test_settings_and_setup.py::test_set_league_id_handler_remove_success_with_others tests/handlers/test_settings_and_setup.py::test_set_league_id_handler_remove_success_and_delete_directory -v`
  預期結果：全部通過 (PASS)

- [ ] **Step 5: 執行完整測試套件確保無 Regression**

  執行測試：
  `python -m pytest tests/test_fetcher.py tests/test_season_utils.py tests/test_storage.py tests/test_config.py tests/handlers/ -q`
  預期結果：所有測試全部通過 (100% PASS)

- [ ] **Step 6: 提交 Commit**

  ```bash
  git add src/handlers/set_league_id_handler.py tests/handlers/test_settings_and_setup.py
  git commit -m "feat(setup): implement remove league ID and data cleaning logic"
  ```
