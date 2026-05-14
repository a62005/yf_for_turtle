# main.py
import logging
import sys
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
        
        fetcher = YahooFantasyFetcher()
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
