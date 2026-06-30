import os
import json
from dotenv import load_dotenv
from contextvars import ContextVar
from typing import Optional

current_chat_id: ContextVar[Optional[str]] = ContextVar("current_chat_id", default=None)

def load_config() -> dict:
    dynamic_server_url = os.environ.get("SERVER_URL")
    
    load_dotenv("league.env", encoding="utf-8")
    load_dotenv(".env", override=True, encoding="utf-8")
    
    current_server_url = os.environ.get("SERVER_URL")
    if (not current_server_url or current_server_url.strip() == "") and dynamic_server_url:
        os.environ["SERVER_URL"] = dynamic_server_url
    
    # 從 current_chat_id 取得 chat_id，讀取 data/security/chat_league_mapping.json 對應的 league_id
    league_id = None
    chat_id = current_chat_id.get() or os.environ.get("LINE_REPLY_TO")
    if chat_id:
        mapping_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "security", "chat_league_mapping.json"))
        if os.path.exists(mapping_file):
            try:
                with open(mapping_file, "r", encoding="utf-8") as f:
                    mapping_data = json.load(f)
                    if mapping_data and chat_id in mapping_data:
                        league_id = str(mapping_data[chat_id])
            except Exception:
                pass
            
    mapping_file = os.getenv("TEAM_MAPPING_FILE", "team_mapping.json")
    season_start = os.getenv("SEASON_START_DATE")
    
    draft_date = os.getenv("DRAFT_DATE")
    next_season_start_date = os.getenv("NEXT_SEASON_START_DATE")
    
    # 讀取聯盟目錄下的 settings.json 來覆寫 DRAFT_DATE 與 next_season_start_date
    lid = league_id or "default"
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    settings_file = os.path.join(base_dir, "data", "league", lid, "settings.json")
    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                settings_data = json.load(f)
                s_draft = settings_data.get("DRAFT_DATE") or settings_data.get("draft_date")
                if s_draft:
                    draft_date = s_draft
                    os.environ["DRAFT_DATE"] = s_draft
                s_next_season = settings_data.get("NEXT_SEASON_START_DATE") or settings_data.get("next_season_start_date")
                if s_next_season:
                    next_season_start_date = s_next_season
                    os.environ["NEXT_SEASON_START_DATE"] = s_next_season
        except Exception:
            pass
    
    return {
        "LEAGUE_ID": league_id, # 可以為 None
        "TEAM_MAPPING_FILE": mapping_file,
        "SEASON_START_DATE": season_start,
        "YAHOO_CLIENT_ID": os.getenv("YAHOO_CLIENT_ID"),
        "YAHOO_CLIENT_SECRET": os.getenv("YAHOO_CLIENT_SECRET"),
        "NGROK_AUTHTOKEN": os.getenv("NGROK_AUTHTOKEN"),
        "LINE_CHANNEL_SECRET": os.getenv("LINE_CHANNEL_SECRET"),
        "LINE_CHANNEL_ACCESS_TOKEN": os.getenv("LINE_CHANNEL_ACCESS_TOKEN"),
        "SERVER_URL": os.getenv("SERVER_URL"),
        "LLM_API_KEY": os.getenv("LLM_API_KEY"),
        "LLM_MODEL": os.getenv("LLM_MODEL"),
        "NEXT_SEASON_START_DATE": next_season_start_date,
        "DRAFT_DATE": draft_date,
        "PRIZE_IMAGE_PATH": os.getenv("PRIZE_IMAGE_PATH"),
        "ENABLE_FOOTBALL_ANALYSIS": os.getenv("ENABLE_FOOTBALL_ANALYSIS", "False").lower() in ("true", "1", "yes")
    }
