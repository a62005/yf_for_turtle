import os
from dotenv import load_dotenv

def load_config() -> dict:
    load_dotenv()
    league_id = os.getenv("LEAGUE_ID")
    if not league_id:
        raise ValueError("LEAGUE_ID is not set in environment or .env file.")
    
    return {
        "LEAGUE_ID": league_id
    }
