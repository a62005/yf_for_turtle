# main.py
import logging
import sys
import os
import json
from src.config import load_config
from src.fetcher import YahooFantasyFetcher
from src.storage import JsonStorage
from src.utils.time_utils import get_fantasy_week, get_pacific_date
from src.visualizer.processor import process_stats_for_visual
from src.visualizer.renderer import render_stats_html
from src.visualizer.capturer import capture_html_to_png

# Set up logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

def main():
    logging.info("[TASK] 開始執行數據更新任務...")
    
    config = None
    today_str = get_pacific_date()
    
    try:
        config = load_config()
        league_id = config["LEAGUE_ID"]
        logging.info(f"[CONFIG] 載入聯盟設定，League ID: {league_id}")
        
        from src.utils.path_utils import get_league_dir, get_league_image_dir, get_league_team_mapping_path
        
        mapping_file = get_league_team_mapping_path(league_id)
        team_mapping = {}
        if os.path.exists(mapping_file):
            try:
                with open(mapping_file, "r", encoding="utf-8") as f:
                    team_mapping = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logging.warning(f"Failed to load team mapping from {mapping_file}: {e}")
                
        fetcher = YahooFantasyFetcher(
            team_mapping=team_mapping,
            client_id=config.get("YAHOO_CLIENT_ID"),
            client_secret=config.get("YAHOO_CLIENT_SECRET"),
            league_id=league_id
        )
        storage = JsonStorage(data_dir=get_league_dir(league_id))

        # 2. Season Stats
        logging.info("[YAHOO] 正在抓取賽季總戰績 (Season Standings)...")
        season_stats = fetcher.fetch_team_stats(league_id)
        season_path = storage.save(season_stats, f"{league_id}_season_stats", overwrite=True)
        logging.info(f"Successfully saved season stats to {season_path}")
        
        # 3. Weekly Stats
        # Test override:
        test_week = os.getenv("TEST_WEEK")
        if test_week:
            current_week = int(test_week)
        else:
            from src.utils.cache_utils import load_league_metadata
            meta = load_league_metadata(league_id)
            today_str = get_pacific_date()
            date_to_week = meta.get("date_to_week", {})
            
            # Use cached mapping if available, otherwise fallback to mathematical calculation
            current_week = date_to_week.get(today_str) or get_fantasy_week(config["SEASON_START_DATE"])
            
            if meta.get("end_week") and current_week > meta["end_week"]:
                current_week = meta["end_week"]
        
        logging.info(f"[YAHOO] 正在抓取第 {current_week} 週週戰績 (Weekly Stats)...")
        weekly_stats = fetcher.fetch_weekly_stats(league_id, current_week)
        
        weekly_path = storage.save(weekly_stats, f"week_{current_week}", sub_dir="weekly", overwrite=True)
        logging.info(f"Successfully saved weekly stats to {weekly_path}")
        
        # 4. Daily Stats
        # Test override:
        test_date = os.getenv("TEST_DATE")
        today_str = test_date if test_date else get_pacific_date()
        
        logging.info(f"[YAHOO] 正在抓取 {today_str} 當日戰績 (Daily Stats)...")
        daily_stats = fetcher.fetch_daily_stats(league_id, today_str)
        roster_counts = fetcher.fetch_batch_rosters(league_id, today_str)
        
        # Merge Today Player data
        for t in daily_stats.get("team_stats", []):
            tid = t.get("team_id")
            if tid in roster_counts:
                t["stats"]["Today Player"] = roster_counts[tid]
                
        daily_path = storage.save(daily_stats, today_str, sub_dir="daily", overwrite=True)
        logging.info(f"Successfully saved daily stats to {daily_path}")
        
        # 5. Visualization
        logging.info("[VISUAL] 正在渲染統計 HTML 模板...")
        try:
            daily_processed = process_stats_for_visual(daily_stats)
            weekly_processed = process_stats_for_visual(weekly_stats)
            
            image_dir = get_league_image_dir(league_id)
            os.makedirs(image_dir, exist_ok=True)
            
            # Combined image
            logging.info("Capturing combined stats image...")
            combined_html = render_stats_html(daily_processed, weekly_processed)
            combined_path = os.path.join(image_dir, f"{today_str}_combined.png")
            capture_html_to_png(combined_html, combined_path)
            logging.info(f"[VISUAL] 圖片製作完成並儲存至: {combined_path}")
            
            # Daily image
            logging.info("Capturing daily stats image...")
            daily_html = render_stats_html(daily_processed)
            daily_path_img = os.path.join(image_dir, f"{today_str}_daily.png")
            capture_html_to_png(daily_html, daily_path_img)
            logging.info(f"[VISUAL] 圖片製作完成並儲存至: {daily_path_img}")
            
            # Weekly image
            logging.info("Capturing weekly stats image...")
            weekly_html = render_stats_html([], weekly_processed)
            weekly_path_img = os.path.join(image_dir, f"week_{current_week}_weekly.png")
            capture_html_to_png(weekly_html, weekly_path_img)
            logging.info(f"[VISUAL] 圖片製作完成並儲存至: {weekly_path_img}")
            
            # Send LINE message if requested
            reply_to = os.getenv("LINE_REPLY_TO")
            if reply_to and config and config.get("LINE_CHANNEL_ACCESS_TOKEN"):
                try:
                    from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, PushMessageRequest, ImageMessage
                    
                    server_url = config.get("SERVER_URL") or "http://localhost:5000"
                    https_url = server_url.replace("http://", "https://")
                    if not https_url.startswith("https://"):
                        https_url = f"https://{https_url.lstrip('https://')}"
                        
                    from src.utils.path_utils import parse_league_id
                    sport, raw_id = parse_league_id(league_id)
                    img_filename = f"{today_str}_combined.png"
                    img_url = f"{https_url}/images/{sport}/{raw_id}/{img_filename}"
                    
                    logging.info(f"[LINE] 正在向 {reply_to} 推送戰績圖片: {img_url}")
                    
                    line_config = Configuration(access_token=config["LINE_CHANNEL_ACCESS_TOKEN"])
                    with ApiClient(line_config) as api_client:
                        messaging_api = MessagingApi(api_client)
                        push_req = PushMessageRequest(
                            to=reply_to,
                            messages=[
                                ImageMessage(
                                    original_content_url=img_url,
                                    preview_image_url=img_url
                                )
                            ]
                        )
                        messaging_api.push_message(push_req)
                    logging.info(f"[LINE] 戰績圖片發送成功！")
                except Exception as le:
                    logging.error(f"[LINE] 發送戰績圖片失敗: {le}")
            
        except Exception as ve:
            logging.error(f"Failed to generate visualization: {ve}")
            reply_to = os.getenv("LINE_REPLY_TO")
            if reply_to and config and config.get("LINE_CHANNEL_ACCESS_TOKEN"):
                try:
                    from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, PushMessageRequest, TextMessage
                    line_config = Configuration(access_token=config["LINE_CHANNEL_ACCESS_TOKEN"])
                    with ApiClient(line_config) as api_client:
                        messaging_api = MessagingApi(api_client)
                        push_req = PushMessageRequest(
                            to=reply_to,
                            messages=[TextMessage(text="戰績數據更新完成，但圖片生成失敗，請稍後重試。")]
                        )
                        messaging_api.push_message(push_req)
                except Exception as le:
                    logging.error(f"[LINE] 發送失敗通知失敗: {le}")

        logging.info("All fetches completed successfully.")
        
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        reply_to = os.getenv("LINE_REPLY_TO")
        token = config.get("LINE_CHANNEL_ACCESS_TOKEN") if config else os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
        if reply_to and token:
            try:
                from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, PushMessageRequest, TextMessage
                line_config = Configuration(access_token=token)
                with ApiClient(line_config) as api_client:
                    messaging_api = MessagingApi(api_client)
                    push_req = PushMessageRequest(
                        to=reply_to,
                        messages=[TextMessage(text="戰績數據更新失敗，請聯絡管理員或稍後重試。")]
                    )
                    messaging_api.push_message(push_req)
            except Exception as le:
                logging.error(f"[LINE] 發送失敗通知失敗: {le}")
        raise
    finally:
        # Clean up lock file if present
        lock_path = os.getenv("FETCH_LOCK_PATH")
        if lock_path and os.path.exists(lock_path):
            try:
                os.remove(lock_path)
                logging.info(f"[LOCK] 成功刪除鎖定檔案: {lock_path}")
            except Exception as le:
                logging.error(f"[LOCK] 刪除鎖定檔案失敗: {le}")

if __name__ == "__main__":
    main()
