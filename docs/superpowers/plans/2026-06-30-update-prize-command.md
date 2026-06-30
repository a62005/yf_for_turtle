# 更新#獎金指令功能與權限實作計畫 (Update #獎金 Command Function & Permissions Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 解除 `#獎金` 的 NBA / 白名單限制，改為所有人可使用（需綁定聯盟）。獎金圖片路徑改為各聯賽獨立的 `image/` 目錄並尋找 `bonus` 或 `bouns` 檔案，若未設置則回覆「尚未設置獎金」。

**Architecture:**
1. 修改 `MiscHandler.execute` 最前端，若未綁定 `league_id` 則直接 `return` 結束（不回覆）。
2. 將 NBA 球種限制移至 `#開季`、`#選秀` 和 `#幫助` 的專屬處理邏輯中。
3. 修改 `_handle_prize` 方法，動態獲取 `sport` 與 `raw_id`，在 `data/league/{sport}/{raw_id}/image` 中找主檔名為 `bouns` 或 `bonus` 的檔案。
4. 若無該檔案則回覆 `尚未設置獎金`；若有則發送新版 URL 格式的 `ImageMessage`。

**Tech Stack:** Python 3.11, pytest, Line Messaging API SDK.

---

### Task 1: 更新限制與攔截邏輯 (Update Constraints & Setup Tests)

**Files:**
- Modify: `src/handlers/misc_handler.py:37-69`
- Modify: `tests/test_misc_handler.py:165-210`

- [ ] **Step 1: 編寫修改後的單元測試**

  修改 `tests/test_misc_handler.py` 中的 `test_execute_prize`：
  1. 測試當沒有綁定 `league_id` 時，輸入 `#獎金` 會直接 return 且不回覆。
  2. 測試當綁定 MLB 聯賽時，輸入 `#獎金` 可以正常處理（不再攔截阻擋）。
  3. 測試當沒有該圖片檔案時，回覆 `尚未設置獎金`。
  4. 測試當圖片檔案存在時，正確發送新版包含 `{sport}/{raw_id}` 的圖片網址。

  替換 `tests/test_misc_handler.py` 中的 `test_execute_prize` 區段：
  ```python
  @patch("src.handlers.misc_handler.load_league_metadata")
  @patch("src.handlers.misc_handler.get_pacific_date")
  @patch("src.handlers.misc_handler.load_config")
  @patch("src.handlers.misc_handler.ApiClient")
  @patch("src.handlers.misc_handler.MessagingApi")
  def test_execute_prize(mock_messaging_api, mock_api_client, mock_load_config, mock_get_pacific, mock_load_meta, mock_event, mock_config):
      handler = MiscHandler()
      mock_event.message.text = "#獎金"
      mock_get_pacific.return_value = "2026-05-29"
      mock_load_meta.return_value = {"end_date": "2026-04-12"}
      
      # 情境 1: 沒有綁定 league_id -> 靜默 return
      mock_load_config.return_value = {"LEAGUE_ID": None, "SERVER_URL": "http://localhost:5000"}
      handler.execute(mock_event, mock_config)
      mock_api_client.assert_not_called()
      
      # 情境 2: 已綁定，但找不到獎金圖片 -> 回覆 "尚未設置獎金"
      mock_api_client.reset_mock()
      mock_load_config.return_value = {"LEAGUE_ID": "mlb.l.62358", "SERVER_URL": "http://localhost:5000"}
      with patch("src.utils.path_utils.parse_league_id", return_value=("mlb", "62358")), \
           patch("os.path.exists", return_value=True), \
           patch("os.listdir", return_value=[]):  # 目錄為空
          handler.execute(mock_event, mock_config)
          
          reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
          assert reply_req.messages[0].text == "尚未設置獎金"
          
      # 情境 3: 已綁定，且有獎金圖片 (如 bouns.png) -> 回覆 ImageMessage
      mock_api_client.reset_mock()
      with patch("src.utils.path_utils.parse_league_id", return_value=("mlb", "62358")), \
           patch("os.path.exists", return_value=True), \
           patch("os.listdir", return_value=["bouns.png"]):
          handler.execute(mock_event, mock_config)
          
          reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
          assert isinstance(reply_req.messages[0], ImageMessage)
          assert reply_req.messages[0].original_content_url == "https://localhost:5000/images/mlb/62358/bouns.png"
  ```

- [ ] **Step 2: 執行測試並驗證失敗**

  執行測試：
  `pytest tests/test_misc_handler.py::test_execute_prize -v`
  預期結果：失敗 (因為 MLB 被前置攔截，且 `_handle_prize` 的路徑與回覆內容仍為舊版)

- [ ] **Step 3: 修改 `MiscHandler.execute` 的權限與未綁定過濾**

  將 [`src/handlers/misc_handler.py:37-69`](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/misc_handler.py#L37-L69) 修改為：
  ```python
      def execute(self, event: MessageEvent, configuration: Configuration) -> None:
          from src.config import load_config
          config = load_config()
          league_id = config.get("LEAGUE_ID")
          
          if not league_id:
              # 未綁定聯賽則靜默退出
              return
  
          user_text = event.message.text.strip()
          match = self.pattern.match(user_text)
          if not match:
              return
  
          # 僅限制 NBA 聯賽的指令
          if user_text in ("#開季", "#選秀"):
              if str(league_id).startswith("mlb.l."):
                  self.reply_text(event, configuration, "⚠️ 此功能目前僅支援 NBA 聯賽。")
                  return
  
          meta = load_league_metadata(league_id) or {}
          end_date = meta.get("end_date")
          today_pacific = get_pacific_date()
          is_offseason = bool(end_date and today_pacific > end_date)
  
          if user_text in ("#開季", "#選秀"):
              if not is_offseason:
                  logging.info(f"Not offseason, ignoring {user_text}")
                  return
  
          if user_text == "#開季":
              self._handle_season_start(event, configuration)
          elif user_text == "#選秀":
              self._handle_draft_countdown(event, configuration)
          elif user_text == "#獎金":
              self._handle_prize(event, configuration)
          elif user_text.startswith("#") and user_text[1:].lower() in ("幫助", "help"):
              # 幫助指令也僅限 NBA
              if str(league_id).startswith("mlb.l."):
                  self.reply_text(event, configuration, "⚠️ 此功能目前僅支援 NBA 聯賽。")
                  return
              self._handle_help(event, configuration)
  ```

- [ ] **Step 4: 實作新版獎金搜尋與發送邏輯 (`_handle_prize`)**

  將 [`src/handlers/misc_handler.py:218-265`](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/misc_handler.py#L218-L265) 替換為以下邏輯：
  ```python
      def _handle_prize(self, event: MessageEvent, configuration: Configuration) -> None:
          config = load_config()
          league_id = config.get("LEAGUE_ID")
          if not league_id:
              return
              
          from src.utils.path_utils import parse_league_id, DATA_DIR
          sport, raw_id = parse_league_id(league_id)
          image_dir = os.path.join(DATA_DIR, "league", sport, raw_id, "image")
          
          target_file = None
          if os.path.exists(image_dir):
              for f in os.listdir(image_dir):
                  base, ext = os.path.splitext(f.lower())
                  if base in ("bouns", "bonus"):
                      target_file = f
                      break
                      
          if not target_file:
              self.reply_text(event, configuration, "尚未設置獎金")
              return
              
          server_url = config.get("SERVER_URL")
          if not server_url:
              logging.info("SERVER_URL not configured, ignoring prize command")
              return
              
          server_url = server_url.rstrip("/")
          if server_url.startswith("http://"):
              server_url = server_url.replace("http://", "https://")
          elif not server_url.startswith("https://"):
              server_url = f"https://{server_url}"
              
          img_url = f"{server_url}/images/{sport}/{raw_id}/{target_file}"
          
          reply_img = ImageMessage(original_content_url=img_url, preview_image_url=img_url)
          with ApiClient(configuration) as api_client:
              MessagingApi(api_client).reply_message(
                  ReplyMessageRequest(
                      reply_token=event.reply_token,
                      messages=[reply_img]
                  )
              )
  ```

- [ ] **Step 5: 重新執行測試驗證通過**

  執行測試：
  `pytest tests/test_misc_handler.py::test_execute_prize -v`
  預期結果：測試全部通過 (PASS)

- [ ] **Step 6: 執行整個項目測試確保無 regression**

  執行測試：
  `python -m pytest tests/test_fetcher.py tests/test_season_utils.py tests/test_storage.py tests/test_config.py tests/test_misc_handler.py -q`
  預期結果：全部通過

- [ ] **Step 7: 提交 Commit**

  ```bash
  git add src/handlers/misc_handler.py tests/test_misc_handler.py
  git commit -m "feat(misc): update #獎金 command with league-specific path, MLB support, and fallback prompt"
  ```
