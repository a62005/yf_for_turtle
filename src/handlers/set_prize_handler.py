import os
import logging
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from src.handlers.base_handler import BaseHandler
from src.config import load_config
from src.utils.session_manager import set_prize_session, clear_prize_session

class SetPrizeHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.requires_whitelist = True
        self.exclude_from_llm = True

    def can_handle(self, user_text: str) -> bool:
        return user_text.strip() == "#設置獎金"

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        config = load_config()
        league_id = config.get("LEAGUE_ID")
        if not league_id:
            self.reply_text(event, configuration, "⚠️ 請先執行 #設置 以綁定聯賽 ID。")
            return

        user_id = getattr(event.source, "user_id", None)
        if not user_id:
            return

        set_prize_session(user_id, duration_sec=60)
        self.reply_text(event, configuration, "👉 請在 60 秒內直接傳送新的獎金圖片：")

    def handle_image(self, event: MessageEvent, configuration: Configuration, image_bytes: bytes) -> None:
        user_id = getattr(event.source, "user_id", None)
        if not user_id:
            return

        config = load_config()
        league_id = config.get("LEAGUE_ID")
        if not league_id:
            clear_prize_session(user_id)
            self.reply_text(event, configuration, "⚠️ 聯賽 ID 尚未綁定。")
            return

        from src.utils.path_utils import parse_league_id, DATA_DIR
        try:
            sport, raw_id = parse_league_id(league_id)
            image_dir = os.path.join(DATA_DIR, "league", sport, raw_id, "image")
            os.makedirs(image_dir, exist_ok=True)

            # 使用時間戳記生成唯一檔名以防 Windows 檔案鎖定導致寫入失敗
            import time
            timestamp = int(time.time())
            target_path = os.path.join(image_dir, f"bonus_{timestamp}.jpg")
            
            with open(target_path, "wb") as f:
                f.write(image_bytes)

            # 寫入成功後，在背景嘗試刪除其他舊的獎金圖檔（刪除失敗也不會影響本次上傳的成功）
            if os.path.exists(image_dir):
                for f in os.listdir(image_dir):
                    if f == f"bonus_{timestamp}.jpg":
                        continue
                    name = f.lower()
                    if name.startswith("bonus") or name.startswith("bouns"):
                        try:
                            os.remove(os.path.join(image_dir, f))
                        except Exception as e:
                            logging.warning(f"Failed to remove old prize file {f} due to Windows file lock: {e}")

            clear_prize_session(user_id)
            self.reply_text(event, configuration, "✅ 成功設定獎金圖片！")
        except Exception as e:
            logging.error(f"[SetPrizeHandler] 儲存獎金圖片失敗: {e}")
            clear_prize_session(user_id)
            self.reply_text(event, configuration, "⚠️ 儲存圖片時發生錯誤，請稍後重試。")

    @property
    def instruction_desc(self) -> str:
        return "#設置獎金 : (限白名單) 調整聯盟的獎金圖片"
