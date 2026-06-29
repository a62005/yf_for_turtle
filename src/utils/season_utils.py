import logging
from datetime import datetime, timedelta
from src.utils.cache_utils import load_league_metadata, save_league_metadata
from src.fetcher import YahooFantasyFetcher

def generate_dates(start_str: str, end_str: str) -> list[str]:
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")
    return [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range((end - start).days + 1)]

def sync_season_metadata(fetcher: YahooFantasyFetcher, league_id: str):
    """
    Fetches base metadata, checks if week_dates are fully populated.
    If not, it fetches all week dates and builds a date_to_week map.
    """
    logging.info("[SYSTEM] 同步賽季中繼資料...")
    old_meta = load_league_metadata(league_id)
    
    try:
        meta = fetcher.fetch_league_metadata(league_id)
    except Exception as e:
        logging.error(f"[SYSTEM] 取得賽季基礎資料時發生異常: {e}")
        meta = {}
    
    if not meta.get("end_week") or not meta.get("start_date"):
        if isinstance(old_meta, dict) and old_meta.get("end_week") and old_meta.get("start_date"):
            logging.warning("[SYSTEM] 無法取得完整的賽季基礎資料，將沿用現有快取。")
            return
        else:
            logging.warning("[SYSTEM] 無法取得完整的賽季基礎資料且無本地歷史快取")
            save_league_metadata(meta, league_id)
            return
        
    week_dates = old_meta.get("week_dates", {})
    date_to_week = old_meta.get("date_to_week", {})
    
    # Check if we need to update week dates
    needs_update = False
    for w in range(1, meta["end_week"] + 1):
        if str(w) not in week_dates:
            needs_update = True
            break
            
    # Also if the league_id changed (new season)
    if old_meta.get("league_id") != meta["league_id"]:
        needs_update = True
        week_dates = {}
        date_to_week = {}
        
    if needs_update:
        logging.info("[SYSTEM] 賽季週次對應表不完整，開始抓取...")
        for w in range(1, meta["end_week"] + 1):
            if str(w) not in week_dates:
                end_date = fetcher.fetch_week_end_date(league_id, w)
                if end_date:
                    week_dates[str(w)] = end_date
                else:
                    logging.warning(f"[SYSTEM] 無法取得第 {w} 週的結束日期")
                    
        # Rebuild date_to_week mapping & Estimate missing week dates
        current_start = meta["start_date"]
        for w in range(1, meta["end_week"] + 1):
            end_date = week_dates.get(str(w))
            
            # 如果結束日期缺失，自動依上週日期估算補全，確保快取完整且下一次啟動不再重複執行與產生 LOG
            if not end_date:
                if current_start:
                    start_dt = datetime.strptime(current_start, "%Y-%m-%d")
                    end_dt_est = start_dt + timedelta(days=6)
                    end_date = end_dt_est.strftime("%Y-%m-%d")
                    week_dates[str(w)] = end_date
                    logging.info(f"[SYSTEM] 第 {w} 週的結束日期缺失，自動估算補全為 {end_date}")
            
            if current_start and end_date:
                dates = generate_dates(current_start, end_date)
                for d in dates:
                    date_to_week[d] = w
                # Next week starts the day after current week ends
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                current_start = (end_dt + timedelta(days=1)).strftime("%Y-%m-%d")
                
        logging.info("[SYSTEM] 賽季週次對應表建立完成")
    else:
        logging.info("[SYSTEM] 賽季週次對應表已存在且完整，無需更新")
        
    meta["week_dates"] = week_dates
    meta["date_to_week"] = date_to_week
    
    save_league_metadata(meta, league_id)
