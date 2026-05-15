# main.py
import logging
import sys
import os
import json
from src.config import load_config
from src.fetcher import YahooFantasyFetcher
from src.storage import JsonStorage
from src.utils.time_utils import get_fantasy_week, get_pacific_date

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

        # 1. Roster Data
        logging.info("Fetching roster data from Yahoo API...")
        roster_data = fetcher.fetch_league_data(league_id)
        roster_path = storage.save(roster_data, league_id)
        logging.info(f"Successfully saved roster data to {roster_path}")

        # 2. Season Stats
        logging.info("Fetching season stats...")
        season_stats = fetcher.fetch_team_stats(league_id)
        season_path = storage.save(season_stats, f"{league_id}_season_stats", overwrite=True)
        logging.info(f"Successfully saved season stats to {season_path}")
        
        # 3. Weekly Stats
        current_week = get_fantasy_week(config["SEASON_START_DATE"])
        logging.info(f"Fetching weekly stats for Week {current_week}...")
        weekly_stats = fetcher.fetch_weekly_stats(league_id, current_week)
        weekly_path = storage.save(weekly_stats, f"week_{current_week}", sub_dir="weekly", overwrite=True)
        logging.info(f"Successfully saved weekly stats to {weekly_path}")
        
        # 4. Daily Stats
        today_str = get_pacific_date()
        logging.info(f"Fetching daily stats for {today_str}...")
        daily_stats = fetcher.fetch_daily_stats(league_id, today_str)
        daily_path = storage.save(daily_stats, today_str, sub_dir="daily", overwrite=True)
        logging.info(f"Successfully saved daily stats to {daily_path}")
        
        logging.info("All fetches completed successfully.")
        
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        # In a real scenario, we might want to exit with a non-zero code
        # sys.exit(1)
        raise

if __name__ == "__main__":
    main()
