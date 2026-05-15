import os
from dotenv import load_dotenv

def load_config() -> dict:
    load_dotenv()
    league_id = os.getenv("LEAGUE_ID")
    if not league_id:
        raise ValueError("LEAGUE_ID is not set in environment or .env file.")
    
    mapping_file = os.getenv("TEAM_MAPPING_FILE", "team_mapping.json")
    # Default to a placeholder if not set
    season_start = os.getenv("SEASON_START_DATE", "2025-10-21")
    
    return {
        "LEAGUE_ID": league_id,
        "TEAM_MAPPING_FILE": mapping_file,
        "SEASON_START_DATE": season_start
    }
