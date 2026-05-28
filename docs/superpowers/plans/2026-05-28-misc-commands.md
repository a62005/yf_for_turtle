# LINE Bot 雜項與資訊指令優化升級 (Misc Commands) 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 實作 `#開季`、`#選秀`、`#獎金` 與 `#幫助`（及大小寫變體）等雜項與資訊指令，支援以 **台北時間 (Asia/Taipei)** 時區進行精準倒數，並支援動態配置獎金分配圖檔與安靜略過機制。

**Architecture:** 新增 `MiscHandler` 繼承 `BaseHandler`，在其中實現台北時區時間差倒數、圖片訊息發送與幫助空接口。擴充 `src/config.py` 以載入新環境變數，並在 `bot.py` 中進行 Handler 註冊。

**Tech Stack:** Python, pytest, pytz, LINE Bot SDK v3

---

### Task 1: 擴充系統環境配置載入與 league.env 設定

**Files:**
- Modify: `src/config.py`
- Modify: `league.env`

- [ ] **Step 1: 編輯 `src/config.py`**
  修改 `load_config()`，在回傳字典中加入 `NEXT_SEASON_START_DATE`、`DRAFT_DATE` 與 `PRIZE_IMAGE_PATH` 欄位。
  
  ```python
  # 修改 src/config.py 中的 return 字典，加入以下三個鍵值對：
  return {
      "LEAGUE_ID": league_id,
      "TEAM_MAPPING_FILE": mapping_file,
      "SEASON_START_DATE": season_start,
      "YAHOO_CLIENT_ID": os.getenv("YAHOO_CLIENT_ID"),
      "YAHOO_CLIENT_SECRET": os.getenv("YAHOO_CLIENT_SECRET"),
      "NGROK_AUTHTOKEN": os.getenv("NGROK_AUTHTOKEN"),
      "LINE_CHANNEL_SECRET": os.getenv("LINE_CHANNEL_SECRET"),
      "LINE_CHANNEL_ACCESS_TOKEN": os.getenv("LINE_CHANNEL_ACCESS_TOKEN"),
      "SERVER_URL": os.getenv("SERVER_URL"),
      "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
      "GEMINI_MODEL": os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
      
      # 新增雜項指令設定項目
      "NEXT_SEASON_START_DATE": os.getenv("NEXT_SEASON_START_DATE"),
      "DRAFT_DATE": os.getenv("DRAFT_DATE"),
      "PRIZE_IMAGE_PATH": os.getenv("PRIZE_IMAGE_PATH")
  }
  ```

- [ ] **Step 2: 編輯 `league.env` 檔案**
  在 `league.env` 的尾端加入新增的雜項指令環境變數範例配置：
  
  ```ini
  NEXT_SEASON_START_DATE=2026-10-20 08:00:00
  DRAFT_DATE=2026-10-15 20:00:00
  PRIZE_IMAGE_PATH=data/images/bonus.png
  ```

- [ ] **Step 3: 執行既有測試確保基本功能未損毀**
  執行：`pytest tests/ -v`
  預期：所有既有測試皆順利 PASS。

- [ ] **Step 4: Commit 變更**
  ```bash
  git add src/config.py league.env
  git commit -m "feat: expand configuration loader for next season countdown and prize image"
  ```

---

### Task 2: 實作全新 MiscHandler 與子指令核心邏輯

**Files:**
- Create: `src/handlers/misc_handler.py`

- [ ] **Step 1: 建立並實作 `src/handlers/misc_handler.py`**
  新增此 Handler，實作指令匹配 `^#(?:開季|選秀|獎金|幫助|[hH][eE][lL][pP])$`，時區倒數轉換、圖片發送、幫助接口。
  
  ```python
  import re
  import os
  import pytz
  import logging
  from datetime import datetime
  from linebot.v3.webhooks import MessageEvent
  from linebot.v3.messaging import ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, ImageMessage, Configuration
  from .base_handler import BaseHandler
  from src.config import load_config
  from src.cache_utils import load_league_metadata

  class MiscHandler(BaseHandler):
      def __init__(self):
          self.pattern = re.compile(r"^#(?:開季|選秀|獎金|幫助|[hH][eE][lL][pP])$")

      def can_handle(self, user_text: str) -> bool:
          return bool(self.pattern.match(user_text.strip()))

      def execute(self, event: MessageEvent, configuration: Configuration) -> None:
          user_text = event.message.text.strip()
          
          # 1. 判斷是否為休賽季
          meta = load_league_metadata()
          end_date = meta.get("end_date")
          
          from src.utils.time_utils import get_pacific_date
          today_pacific = get_pacific_date()
          
          is_offseason = end_date and today_pacific > end_date

          # 2. 路由分派
          if user_text == "#開季":
              if not is_offseason:
                  logging.info("[MiscHandler] Skip #開季 since it is not offseason.")
                  return
              self._handle_season_start(event, configuration)
          elif user_text == "#選秀":
              if not is_offseason:
                  logging.info("[MiscHandler] Skip #選秀 since it is not offseason.")
                  return
              self._handle_draft_countdown(event, configuration)
          elif user_text == "#獎金":
              self._handle_prize(event, configuration)
          elif user_text.startswith("#") and user_text[1:].lower() in ["幫助", "help"]:
              self._handle_help(event, configuration)

      def _calculate_countdown(self, target_time_str: str) -> str:
          """計算當前台北時間到目標台北時間的倒數，並格式化為繁體中文"""
          taipei_tz = pytz.timezone("Asia/Taipei")
          now_taipei = datetime.now(taipei_tz)
          
          try:
              target_naive = datetime.strptime(target_time_str, "%Y-%m-%d %H:%M:%S")
              target_taipei = taipei_tz.localize(target_naive)
          except Exception as e:
              logging.error(f"[MiscHandler] Failed to parse target time string '{target_time_str}': {e}")
              return ""

          if now_taipei >= target_taipei:
              return "已經到達！"

          diff = target_taipei - now_taipei
          days = diff.days
          hours, remainder = divmod(diff.seconds, 3600)
          minutes, _ = divmod(remainder, 60)
          
          return f"{days} 天 {hours} 小時 {minutes} 分鐘"

      def _handle_season_start(self, event: MessageEvent, configuration: Configuration) -> None:
          config = load_config()
          target_str = config.get("NEXT_SEASON_START_DATE")
          if not target_str:
              logging.warning("[MiscHandler] NEXT_SEASON_START_DATE not configured.")
              return
              
          countdown_text = self._calculate_countdown(target_str)
          if not countdown_text:
              return
              
          reply_text = f"🏀 距離 2026-27 新賽季開季還有：\n👉 {countdown_text}"
          self.reply_text(event, configuration, reply_text)

      def _handle_draft_countdown(self, event: MessageEvent, configuration: Configuration) -> None:
          config = load_config()
          target_str = config.get("DRAFT_DATE")
          if not target_str:
              logging.warning("[MiscHandler] DRAFT_DATE not configured.")
              return
              
          countdown_text = self._calculate_countdown(target_str)
          if not countdown_text:
              return
              
          reply_text = f"⚔️ 距離 2026-27 聯盟選秀還有：\n👉 {countdown_text}"
          self.reply_text(event, configuration, reply_text)

      def _handle_prize(self, event: MessageEvent, configuration: Configuration) -> None:
          config = load_config()
          path = config.get("PRIZE_IMAGE_PATH")
          if not path or not os.path.exists(path):
              logging.warning(f"[MiscHandler] Prize image not found or not configured: {path}")
              return
              
          server_url = config.get("SERVER_URL")
          if not server_url:
              logging.error("[MiscHandler] SERVER_URL is not configured.")
              return
              
          filename = os.path.basename(path)
          image_url = f"{server_url}/images/{filename}"
          
          with ApiClient(configuration) as api_client:
              MessagingApi(api_client).reply_message(
                  ReplyMessageRequest(
                      reply_token=event.reply_token,
                      messages=[ImageMessage(original_content_url=image_url, preview_image_url=image_url)]
                  )
              )

      def _handle_help(self, event: MessageEvent, configuration: Configuration) -> None:
          # 幫助接口，本期先開好接口並安靜略過
          logging.info("[MiscHandler] Triggered #幫助/help interface, skipped as placeholder.")
          pass

      def reply_text(self, event: MessageEvent, configuration: Configuration, text: str) -> None:
          with ApiClient(configuration) as api_client:
              MessagingApi(api_client).reply_message(
                  ReplyMessageRequest(
                      reply_token=event.reply_token,
                      messages=[TextMessage(text=text)]
                  )
              )
  ```

- [ ] **Step 2: Commit 變更**
  ```bash
  git add src/handlers/misc_handler.py
  git commit -m "feat: implement MiscHandler for offseason countdowns and prize image reply"
  ```

---

### Task 3: 註冊 Handler 與生成預設獎金圖檔

**Files:**
- Modify: `bot.py`
- Create: `data/images/bonus.png` (由 AI 繪圖產生或建立)

- [ ] **Step 1: 在 `bot.py` 中註冊 `MiscHandler`**
  編輯 `bot.py`，導入並將 `MiscHandler` 實例註冊至 `CommandDispatcher` 中。
  
  ```python
  # 在 bot.py 的 Import 區域加入：
  from src.handlers.misc_handler import MiscHandler
  
  # 在 bot.py 的註冊 Handler 區域加入：
  dispatcher.register(StatsHandler())
  dispatcher.register(PlayerHandler())
  dispatcher.register(UserStatsHandler())
  dispatcher.register(MatchupHandler())
  dispatcher.register(MiscHandler()) # 註冊新 Handler
  ```

- [ ] **Step 2: 產生高質感預設獎金圖檔**
  建立 `data/images` 資料夾（若不存在），並在此位置寫入一張金黃色 NBA 獎盃質感背景的範例圖片作為 `bonus.png`。

- [ ] **Step 3: Commit 變更**
  ```bash
  git add bot.py data/images/bonus.png
  git commit -m "chore: register MiscHandler and seed default prize image"
  ```

---

### Task 4: 撰寫全面單元測試與專案驗證

**Files:**
- Create: `tests/test_misc_handler.py`

- [ ] **Step 1: 建立並實作 `tests/test_misc_handler.py`**
  針對 `MiscHandler` 的匹配性、台北時區倒數計算、休賽季判定與安靜略過、圖檔發送機制、幫助接口進行測試。
  
  ```python
  import os
  import pytest
  from unittest.mock import MagicMock, patch
  from datetime import datetime
  import pytz
  from src.handlers.misc_handler import MiscHandler

  def test_misc_handler_can_handle():
      handler = MiscHandler()
      # 應該匹配
      assert handler.can_handle("#開季") is True
      assert handler.can_handle("#選秀") is True
      assert handler.can_handle("#獎金") is True
      assert handler.can_handle("#幫助") is True
      assert handler.can_handle("#help") is True
      assert handler.can_handle("#HElp") is True
      assert handler.can_handle("#Help  ") is True
      # 排除不合法
      assert handler.can_handle("#開賽季") is False
      assert handler.can_handle("#選秀會") is False
      assert handler.can_handle("#獎金分發") is False
      assert handler.can_handle("#helper") is False

  @patch("src.handlers.misc_handler.load_league_metadata")
  @patch("src.handlers.misc_handler.load_config")
  @patch("src.handlers.misc_handler.MiscHandler.reply_text")
  def test_season_start_and_draft_active_season(mock_reply_text, mock_load_config, mock_load_metadata, mocker):
      # 模擬在賽季中 (非休賽季)
      # today = "2026-02-01", end_date = "2026-04-12" -> offseason = False
      mock_load_metadata.return_value = {"end_date": "2026-04-12"}
      mocker.patch("src.handlers.misc_handler.get_pacific_date", return_value="2026-02-01")
      
      mock_load_config.return_value = {
          "NEXT_SEASON_START_DATE": "2026-10-20 08:00:00",
          "DRAFT_DATE": "2026-10-15 20:00:00"
      }
      
      handler = MiscHandler()
      
      # 測試 #開季
      mock_event = MagicMock()
      mock_event.message.text = "#開季"
      mock_config = MagicMock()
      handler.execute(mock_event, mock_config)
      mock_reply_text.assert_not_called()
      
      # 測試 #選秀
      mock_event.message.text = "#選秀"
      handler.execute(mock_event, mock_config)
      mock_reply_text.assert_not_called()

  @patch("src.handlers.misc_handler.load_league_metadata")
  @patch("src.handlers.misc_handler.load_config")
  @patch("src.handlers.misc_handler.MiscHandler.reply_text")
  def test_season_start_countdown_offseason(mock_reply_text, mock_load_config, mock_load_metadata, mocker):
      # 模擬休賽季期間 (today = "2026-05-28", end_date = "2026-04-12" -> offseason = True)
      mock_load_metadata.return_value = {"end_date": "2026-04-12"}
      mocker.patch("src.handlers.misc_handler.get_pacific_date", return_value="2026-05-28")
      
      mock_load_config.return_value = {
          "NEXT_SEASON_START_DATE": "2026-10-20 08:00:00"
      }
      
      # 固定當前的台北時間進行測試
      # 2026-05-28 23:00:00 (台北時間)
      taipei_tz = pytz.timezone("Asia/Taipei")
      fixed_now = taipei_tz.localize(datetime(2026, 5, 28, 23, 0, 0))
      
      class MockedDatetime:
          @classmethod
          def now(cls, tz=None):
              return fixed_now
          @classmethod
          def strptime(cls, string, fmt):
              return datetime.strptime(string, fmt)

      mocker.patch("src.handlers.misc_handler.datetime", MockedDatetime)
      
      handler = MiscHandler()
      mock_event = MagicMock()
      mock_event.message.text = "#開季"
      mock_config = MagicMock()
      
      handler.execute(mock_event, mock_config)
      
      # 倒數計算：
      # 2026-10-20 08:00:00 - 2026-05-28 23:00:00
      # 剩餘：144 天 9 小時 0 分鐘
      mock_reply_text.assert_called_once()
      call_args = mock_reply_text.call_args[0]
      assert "🏀 距離 2026-27 新賽季開季還有" in call_args[2]
      assert "144 天 9 小時 0 分鐘" in call_args[2]

  @patch("src.handlers.misc_handler.load_league_metadata")
  @patch("src.handlers.misc_handler.load_config")
  @patch("src.handlers.misc_handler.ApiClient")
  @patch("src.handlers.misc_handler.MessagingApi")
  def test_handle_prize_image(mock_messaging_api, mock_api_client, mock_load_config, mock_load_metadata, mocker):
      mock_load_metadata.return_value = {"end_date": "2026-04-12"}
      
      mock_load_config.return_value = {
          "PRIZE_IMAGE_PATH": "data/images/bonus.png",
          "SERVER_URL": "https://testurl.ngrok-free.app"
      }
      
      handler = MiscHandler()
      
      # 1. 當檔案不存在時，應安靜退出
      mocker.patch("os.path.exists", return_value=False)
      mock_event = MagicMock()
      mock_event.message.text = "#獎金"
      mock_config = MagicMock()
      
      handler.execute(mock_event, mock_config)
      mock_messaging_api.return_value.reply_message.assert_not_called()
      
      # 2. 當檔案存在時，應傳送 ImageMessage
      mocker.patch("os.path.exists", return_value=True)
      handler.execute(mock_event, mock_config)
      
      mock_messaging_api.return_value.reply_message.assert_called_once()
      reply_arg = mock_messaging_api.return_value.reply_message.call_args[0][0]
      image_msg = reply_arg.messages[0]
      assert image_msg.original_content_url == "https://testurl.ngrok-free.app/images/bonus.png"
      assert image_msg.preview_image_url == "https://testurl.ngrok-free.app/images/bonus.png"

  @patch("src.handlers.misc_handler.load_league_metadata")
  @patch("src.handlers.misc_handler.ApiClient")
  @patch("src.handlers.misc_handler.MessagingApi")
  def test_handle_help_quiet_exit(mock_messaging_api, mock_api_client, mock_load_metadata):
      handler = MiscHandler()
      mock_event = MagicMock()
      mock_event.message.text = "#幫助"
      mock_config = MagicMock()
      
      handler.execute(mock_event, mock_config)
      
      # 應直接 return 略過，無任何 API 發送
      mock_messaging_api.return_value.reply_message.assert_not_called()
  ```

- [ ] **Step 2: 運行測試以驗證測試失敗**
  執行：`pytest tests/test_misc_handler.py -v`
  預期：FAIL (因為程式碼與檔案均未真正寫入)。

- [ ] **Step 3: 執行全專案測試套件以驗證最後 100% 通過**
  執行：`PYTHONPATH=. pytest tests/ -v`
  預期：PASS。

- [ ] **Step 4: Commit 變更**
  ```bash
  git add tests/test_misc_handler.py
  git commit -m "test: add comprehensive unit tests for MiscHandler"
  ```
