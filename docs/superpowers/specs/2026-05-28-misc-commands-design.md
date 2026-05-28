# 設計規格書：LINE Bot 雜項與資訊指令優化升級 (Misc Commands)

本設計規格書詳細規劃了如何在 LINE Bot 中新增一組雜項與資訊查詢指令：`#開季`、`#選秀`、`#獎金` 與 `#幫助`（及變體）。此設計支援以 **台北時間 (Asia/Taipei)** 為基準進行精準倒數，並能動態依據配置檔傳送獎金分配圖檔，兼顧功能靈活性與架構簡潔度。

---

## 1. 背景與目標

### 1.1 新增功能點
1.  **#開季**：查詢距離新賽季開季時間還有多久（僅限休賽季期間）。
2.  **#選秀**：查詢距離聯盟選秀時間還有多久（僅限休賽季期間）。
3.  **#獎金**：回傳獎金分配的圖檔。
4.  **#幫助 / #help / #Help / #HElp 等**：提供功能說明的接口（本期先開好接口並安靜略過，留待後續補充）。

### 1.2 設計原則
-  **台北時間對齊**：開季與選秀的剩餘時間計算，統一在 **台北時間 (`Asia/Taipei`)** 時區進行。
-  **靈活配置**：時間字串、獎金圖檔路徑全部透過 `league.env` 設定，程式碼中無 Hardcode，便於年年修改。
-  **防打擾原則**：
    - 在非休賽季期間，`#開季` 與 `#選秀` 自動安靜略過，不做任何回覆。
    - 若未配置時間或圖檔不存在，則安靜略過。
-  **代碼高度內聚**：所有雜項指令統一收攏在全新的 `MiscHandler` 中，並註冊至 `CommandDispatcher`。

---

## 2. 詳細技術設計

### 2.1 環境變數與配置變更
我們將在 `src/config.py` 的 `load_config()` 方法中擴充讀取以下三個新變數：

- `NEXT_SEASON_START_DATE`：新賽季開季時間（例如 `2026-10-20 08:00:00`）。
- `DRAFT_DATE`：聯盟選秀時間（例如 `2026-10-15 20:00:00`）。
- `PRIZE_IMAGE_PATH`：獎金圖檔在專案中的本地路徑（例如 `data/images/bonus.png`）。

#### 📝 `league.env` 的新增配置範例
```ini
NEXT_SEASON_START_DATE=2026-10-20 08:00:00
DRAFT_DATE=2026-10-15 20:00:00
PRIZE_IMAGE_PATH=data/images/bonus.png
```

---

### 2.2 實作全新 `MiscHandler` (`src/handlers/misc_handler.py`)
`MiscHandler` 繼承 `BaseHandler`，專責處理此批雜項與資訊指令：

```python
import os
import pytz
import logging
from datetime import datetime
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration, TextMessage, ImageMessage, ApiClient, MessagingApi, ReplyMessageRequest
from .base_handler import BaseHandler
from src.config import load_config
from src.cache_utils import load_league_metadata

class MiscHandler(BaseHandler):
    def __init__(self):
        # 匹配 #幫助、#help 及其大小寫變體
        self.pattern = re.compile(r"^#(?:開季|選秀|獎金|幫助|[hH][eE][lL][pP])$")

    def can_handle(self, user_text: str) -> bool:
        return bool(self.pattern.match(user_text.strip()))

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = event.message.text.strip()
        
        # 1. 判斷是否為休賽季
        meta = load_league_metadata()
        end_date = meta.get("end_date") # 例如 2026-04-12
        
        from src.utils.time_utils import get_pacific_date
        today_pacific = get_pacific_date()
        
        is_offseason = end_date and today_pacific > end_date

        # 2. 控制流分發
        if user_text == "#開季":
            if not is_offseason:
                return
            self._handle_season_start(event, configuration)
        elif user_text == "#選秀":
            if not is_offseason:
                return
            self._handle_draft_countdown(event, configuration)
        elif user_text == "#獎金":
            self._handle_prize(event, configuration)
        elif user_text.startswith("#") and user_text[1:].lower() in ["幫助", "help"]:
            self._handle_help(event, configuration)
```

#### 🔹 倒數計時計算邏輯 (`Asia/Taipei` 時區)
```python
def _calculate_countdown(self, target_time_str: str) -> str:
    """計算當前台北時間到目標台北時間的倒數，並格式化為繁體中文"""
    taipei_tz = pytz.timezone("Asia/Taipei")
    now_taipei = datetime.now(taipei_tz)
    
    try:
        # 將設定的時間解析為台北時間
        target_naive = datetime.strptime(target_time_str, "%Y-%m-%d %H:%M:%S")
        target_taipei = taipei_tz.localize(target_naive)
    except ValueError:
        logging.error(f"Failed to parse target time string: {target_time_str}")
        return ""

    if now_taipei >= target_taipei:
        return "已經到達！"

    diff = target_taipei - now_taipei
    days = diff.days
    hours, remainder = divmod(diff.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    return f"{days} 天 {hours} 小時 {minutes} 分鐘"
```

#### 🔹 子方法具體實作
```python
def _handle_season_start(self, event: MessageEvent, configuration: Configuration) -> None:
    config = load_config()
    target_str = config.get("NEXT_SEASON_START_DATE")
    if not target_str:
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
        logging.warning(f"Prize image not found or not configured: {path}")
        return
        
    server_url = config.get("SERVER_URL")
    if not server_url:
        logging.error("SERVER_URL is not configured.")
        return
        
    filename = os.path.basename(path)
    image_url = f"{server_url}/images/{filename}"
    
    # 透過 LINE Bot API 發送圖片
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[ImageMessage(original_content_url=image_url, preview_image_url=image_url)]
            )
        )

def _handle_help(self, event: MessageEvent, configuration: Configuration) -> None:
    # 幫助接口，本期先開好接口並安靜略過
    pass
```

---

## 3. 測試計畫 (Test Plan)

### 3.1 單元測試擴充
我們將新增 `/tests/test_misc_handler.py` 來全面覆蓋雜項指令。

#### 🔹 測項一：驗證 `can_handle` 匹配性
- 下列輸入預期 `True`：`#開季`、`#選秀`、`#獎金`、`#幫助`、`#help`、`#HElp`、`#Help  `。
- 下列輸入預期 `False`：`#開賽季`、`#選秀會`、`#獎金分發`、`#helper`。

#### 🔹 測項二：驗證 `#開季` 與 `#選秀`
- 模擬非休賽季 ──► 驗證安靜退出。
- 模擬休賽季，但未配置變數 ──► 驗證安靜退出。
- 模擬休賽季且有配置變數 ──► 驗證回覆文字格式符合 `距離...還有...`。

#### 🔹 測項三：驗證 `#獎金`
- 模擬未配置或檔案不存在 ──► 驗證安靜退出。
- 模擬配置且檔案存在 ──► 驗證回傳 `ImageMessage`，且下載 URL 的 domain 為 `SERVER_URL` 的 ngrok。

#### 🔹 測項四：驗證 `#幫助`
- 驗證接口調用成功且安靜略過（不會呼叫任何發送 API）。
