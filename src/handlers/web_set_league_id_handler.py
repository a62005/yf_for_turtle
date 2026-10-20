import os
import json
import shutil
import logging
from urllib.parse import quote
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from src.handlers.base_handler import BaseHandler
from src.config import load_config, current_chat_id
from src.utils.path_utils import DATA_DIR, get_league_dir
from src.utils.security import security_manager
from src.utils.session_manager import (
    register_session,
    get_active_session,
    clear_active_session,
    LeagueIdSession,
    RemoveLeagueSession,
)
from src.web_login_bridge import (
    get_league_storage_state_path,
    verify_league_web_access,
)


def build_mobile_web_login_url(league_id: str, chat_id: str = None) -> str:
    """組合供手機端開啟的遠端 Yahoo 網頁登入網址。"""
    config = load_config()
    server_url = os.environ.get("SERVER_URL") or config.get("SERVER_URL") or "http://localhost:5001"
    https_url = server_url.replace("http://", "https://").rstrip("/")
    if not https_url.startswith("https://"):
        https_url = f"https://{https_url.lstrip('https://')}"
    cid = chat_id or current_chat_id.get() or "default"
    return f"{https_url}/yahoo/web-login?league_id={quote(str(league_id))}&chat_id={quote(str(cid))}"


class WebSetLeagueIdHandler(BaseHandler):
    """網頁登入版之聯盟 ID 綁定處理器（不呼叫北美受限的 Yahoo API，改用手機遠端網頁登入授權）。"""

    def __init__(self):
        super().__init__()
        self.requires_manager = True
        self.exclude_from_llm = True

    def can_handle(self, user_text: str) -> bool:
        text = user_text.strip()
        return (
            text.startswith("#設置聯盟ID")
            or text == "#移除聯盟ID"
            or text == "#確定移除聯盟ID"
        )

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = event.message.text.strip()
        user_id = getattr(event.source, "user_id", None)

        if user_text == "#移除聯盟ID":
            if user_id:
                register_session(RemoveLeagueSession(user_id, duration_sec=60))
            else:
                self.reply_text(event, configuration, "⚠️ 無法獲取您的 User ID，請重新嘗試。")
                return

            from src.visualizer.flex_builder import build_button_menu_card
            flex_dict = build_button_menu_card(
                "確定要移除聯盟綁定嗎？",
                None,
                [("確定移除", "#確定移除聯盟ID"), ("取消", "")]
            )
            self.reply_flex(event, configuration, "確認移除聯盟綁定", flex_dict)
            return

        if user_text == "#確定移除聯盟ID":
            session = get_active_session(user_id) if user_id else None
            if not isinstance(session, RemoveLeagueSession):
                return
            if user_id:
                clear_active_session(user_id)

            chat_id = current_chat_id.get() or "default"
            security_dir = os.path.join(DATA_DIR, "security")
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

            removed_league_id = mapping.pop(str(chat_id))
            try:
                os.makedirs(security_dir, exist_ok=True)
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(mapping, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logging.error(f"[WebSetLeagueIdHandler] 寫入映射表失敗: {e}")
                self.reply_text(event, configuration, "⚠️ 解除綁定時寫入設定檔失敗。")
                return

            has_others = any(str(val) == str(removed_league_id) for val in mapping.values())
            if not has_others:
                league_dir = get_league_dir(removed_league_id)
                if os.path.exists(league_dir):
                    try:
                        for item in os.listdir(league_dir):
                            item_path = os.path.join(league_dir, item)
                            if item in (".yahoofantasy", "oauth2.json") or "yahoo" in item or "oauth" in item:
                                continue
                            if os.path.isdir(item_path):
                                shutil.rmtree(item_path)
                            else:
                                os.remove(item_path)
                    except Exception as delete_error:
                        logging.error(f"[WebSetLeagueIdHandler] 清理聯賽目錄失敗: {delete_error}")

            self.reply_text(event, configuration, "✅ 已成功解除此群組的聯盟綁定。")
            return

        if user_text == "#設置聯盟ID":
            from src.visualizer.flex_builder import build_button_menu_card
            flex_dict = build_button_menu_card(
                "選擇要設置的運動項目",
                None,
                [("NBA 籃球", "#設置聯盟ID nba"), ("MLB 棒球", "#設置聯盟ID mlb")]
            )
            self.reply_flex(event, configuration, "請選擇要設置的運動項目", flex_dict)
            return

        parts = user_text.split()
        if len(parts) == 2 and parts[1].lower() in ["nba", "mlb"]:
            sport = parts[1].lower()
            if user_id:
                register_session(LeagueIdSession(user_id, sport, duration_sec=60))
                sport_name = "NBA 籃球" if sport == "nba" else "MLB 棒球"
                self.reply_text(event, configuration, f"您選擇了 {sport_name}。請在 60 秒內輸入您的聯盟 ID（純數字，例如 49432）：")
            else:
                self.reply_text(event, configuration, "⚠️ 無法獲取您的 User ID，請重新嘗試。")
            return

        session = get_active_session(user_id) if user_id else None
        if isinstance(session, LeagueIdSession) and len(parts) == 2 and parts[1].isdigit():
            sport = session.sport
            target_id = f"{sport}.l.{parts[1]}"
            clear_active_session(user_id)
        else:
            if len(parts) < 2:
                self.reply_text(event, configuration, "⚠️ 指令格式錯誤。")
                return
            target_id = parts[1].strip()
            if target_id.isdigit():
                target_id = f"nba.l.{target_id}"
            elif not target_id.startswith("nba.l.") and not target_id.startswith("mlb.l."):
                target_id = f"nba.l.{target_id}"

        roles = security_manager._load_json(security_manager.league_roles_path, {})
        league_data = roles.get(target_id)
        if league_data and isinstance(league_data, dict):
            manager_id = league_data.get("manager")
            if manager_id and manager_id != user_id and not security_manager.is_super_admin(user_id):
                self.reply_text(event, configuration, f"⚠️ 設置失敗，該聯盟 ID ({target_id}) 已由其他管理員管理。")
                return

        # 先將此聊天室與聯賽 ID 綁定記錄下來
        chat_id = current_chat_id.get() or "default"
        try:
            self._update_league_id(target_id, user_id)
        except Exception as fe:
            logging.error(f"[WebSetLeagueIdHandler] 寫入綁定設定失敗: {fe}")
            self.reply_text(event, configuration, "⚠️ 儲存聯盟綁定設定時發生錯誤。")
            return

        # 憑證複用：若此管理員在其他聯盟已有 yahoo_web_state.json，先嘗試複製過去驗證
        state_path = get_league_storage_state_path(target_id)
        if user_id and not os.path.exists(state_path):
            for prev_lid, ldata in roles.items():
                if isinstance(ldata, dict) and ldata.get("manager") == user_id and prev_lid != target_id:
                    prev_state = get_league_storage_state_path(prev_lid)
                    if os.path.exists(prev_state):
                        try:
                            shutil.copy2(prev_state, state_path)
                            break
                        except Exception:
                            pass

        # 檢查現有網頁登入狀態是否可直接存取該聯盟頁面
        if verify_league_web_access(target_id):
            security_manager.set_league_authorized(target_id, True)
            self.reply_text(event, configuration, f"✅ 成功將此聊天室綁定至聯賽 ID：{target_id}")
            return

        # 若尚未登入或無該聯盟權限，提供手機端遠端網頁登入網址
        security_manager.set_league_authorized(target_id, False)
        login_url = build_mobile_web_login_url(target_id, chat_id)
        msg = (
            f"🔐 已記錄聯賽 ID：{target_id}\n"
            f"目前尚未具備該聯賽的網頁登入權限，請點擊下方網址於手機完成 Yahoo 帳號登入：\n"
            f"{login_url}"
        )
        self.reply_text(event, configuration, msg)

    def _update_league_id(self, league_id: str, user_id: str = None) -> None:
        chat_id = current_chat_id.get() or "default"
        security_dir = os.path.join(DATA_DIR, "security")
        os.makedirs(security_dir, exist_ok=True)
        config_path = os.path.join(security_dir, "chat_league_mapping.json")

        mapping = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    mapping = json.load(f)
            except Exception:
                mapping = {}

        mapping[str(chat_id)] = str(league_id)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)

        if user_id:
            security_manager.set_league_owner(league_id, user_id)

    @property
    def instruction_desc(self) -> str:
        return "#設置聯盟ID <ID> : (限管理員) 設置並透過網頁登入綁定指定之 Yahoo 聯盟 ID"
