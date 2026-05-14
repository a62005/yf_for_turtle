# main.py
import logging
import sys
import os
import json
from src.config import load_config
from src.fetcher import YahooFantasyFetcher
from src.storage import JsonStorage

# Set up logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

def main():
    logging.info("Starting Yahoo Fantasy Scraper...")
    
    try:
        config = load_config()
        league_id = config["LEAGUE_ID"]
        logging.info(f"Loaded config for League ID: {league_id}")
        
        mapping_file = config.get("TEAM_MAPPING_FILE", "team_mapping.json")
        team_mapping = {}
        if os.path.exists(mapping_file):
            try:
                with open(mapping_file, "r", encoding="utf-8") as f:
                    team_mapping = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logging.warning(f"Failed to load team mapping from {mapping_file}: {e}")
                
        fetcher = YahooFantasyFetcher(team_mapping=team_mapping)
        logging.info("Fetching data from Yahoo API...")
        # Note: This will attempt to authenticate if oauth2.json is missing
        data = fetcher.fetch_league_data(league_id)
        
        storage = JsonStorage()
        filepath = storage.save(data, league_id)
        logging.info(f"Successfully saved data to {filepath}")
        
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        # In a real scenario, we might want to exit with a non-zero code
        # sys.exit(1)
        raise

if __name__ == "__main__":
    main()
