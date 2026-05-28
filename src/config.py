import os
from dotenv import load_dotenv

def load_config() -> dict:
    # 1. 載入公開的聯盟設定 (不覆蓋系統環境變數)
    load_dotenv("league.env", encoding="utf-8")
    
    # 2. 載入私密設定 (override=True 以便覆蓋 league.env 中的值)
    load_dotenv(".env", override=True, encoding="utf-8")
    
    league_id = os.getenv("LEAGUE_ID")
    if not league_id:
        raise ValueError("LEAGUE_ID is not set in environment, .env, or league.env file.")
    
    mapping_file = os.getenv("TEAM_MAPPING_FILE", "team_mapping.json")
    season_start = os.getenv("SEASON_START_DATE")
    
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
        "GEMINI_MODEL": os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    }
