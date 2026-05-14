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
        storage = JsonStorage()

        logging.info("Fetching roster data from Yahoo API...")
        roster_data = fetcher.fetch_league_data(league_id)
        roster_filepath = storage.save(roster_data, league_id)
        logging.info(f"Successfully saved roster data to {roster_filepath}")
        
        logging.info("Fetching team stats from Yahoo API...")
        stats_data = fetcher.fetch_team_stats(league_id)
        stats_filepath = storage.save(stats_data, f"{league_id}_stats")
        logging.info(f"Successfully saved team stats to {stats_filepath}")
        
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        # In a real scenario, we might want to exit with a non-zero code
        # sys.exit(1)
        raise

if __name__ == "__main__":
    main()
