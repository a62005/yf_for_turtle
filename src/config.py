import os
import json
from dotenv import load_dotenv

def load_config() -> dict:
    dynamic_server_url = os.environ.get("SERVER_URL")
    
    load_dotenv("league.env", encoding="utf-8")
    load_dotenv(".env", override=True, encoding="utf-8")
    
    current_server_url = os.environ.get("SERVER_URL")
    if (not current_server_url or current_server_url.strip() == "") and dynamic_server_url:
        os.environ["SERVER_URL"] = dynamic_server_url
    
    # 僅從動態設定檔 data/security/league_config.json 讀取聯盟 ID，不再從環境變數或 env 讀取
    league_id = None
    security_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "security", "league_config.json"))
    if os.path.exists(security_file):
        try:
            with open(security_file, "r", encoding="utf-8") as f:
                sec_data = json.load(f)
                if sec_data.get("LEAGUE_ID"):
                    league_id = str(sec_data["LEAGUE_ID"])
        except Exception:
            pass
            
    mapping_file = os.getenv("TEAM_MAPPING_FILE", "team_mapping.json")
    season_start = os.getenv("SEASON_START_DATE")
    
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
        "NEXT_SEASON_START_DATE": os.getenv("NEXT_SEASON_START_DATE"),
        "DRAFT_DATE": os.getenv("DRAFT_DATE"),
        "PRIZE_IMAGE_PATH": os.getenv("PRIZE_IMAGE_PATH"),
        "ENABLE_FOOTBALL_ANALYSIS": os.getenv("ENABLE_FOOTBALL_ANALYSIS", "False").lower() in ("true", "1", "yes")
    }
