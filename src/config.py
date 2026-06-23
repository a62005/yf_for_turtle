import os
from dotenv import load_dotenv

def load_config() -> dict:
    # 備份由 bot.py 動態設定的 SERVER_URL (例如 ngrok 自動網址)
    dynamic_server_url = os.environ.get("SERVER_URL")
    
    # 1. 載入公開的聯盟設定 (不覆蓋系統環境變數)
    load_dotenv("league.env", encoding="utf-8")
    
    # 2. 載入私密設定 (override=True 以便覆蓋 league.env 中的值)
    load_dotenv(".env", override=True, encoding="utf-8")
    
    # 若載入後變為空值或空字串，但原先有備份的動態設定，則將其還原
    current_server_url = os.environ.get("SERVER_URL")
    if (not current_server_url or current_server_url.strip() == "") and dynamic_server_url:
        os.environ["SERVER_URL"] = dynamic_server_url
    
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
        "LLM_API_KEY": os.getenv("LLM_API_KEY"),
        "LLM_MODEL": os.getenv("LLM_MODEL"),
        "NEXT_SEASON_START_DATE": os.getenv("NEXT_SEASON_START_DATE"),
        "DRAFT_DATE": os.getenv("DRAFT_DATE"),
        "PRIZE_IMAGE_PATH": os.getenv("PRIZE_IMAGE_PATH"),
        "MAX_EVENT_DELAY_SECONDS": os.getenv("MAX_EVENT_DELAY_SECONDS", "10.0"),
        "ENABLE_FOOTBALL_ANALYSIS": os.getenv("ENABLE_FOOTBALL_ANALYSIS", "False").lower() in ("true", "1", "yes")
    }
