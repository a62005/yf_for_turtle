import os
from dotenv import load_dotenv

def load_config() -> dict:
    load_dotenv()
    league_id = os.getenv("LEAGUE_ID")
    if not league_id:
        raise ValueError("LEAGUE_ID is not set in environment or .env file.")
    
    mapping_file = os.getenv("TEAM_MAPPING_FILE", "team_mapping.json")
    
    return {
        "LEAGUE_ID": league_id,
        "TEAM_MAPPING_FILE": mapping_file
    }
