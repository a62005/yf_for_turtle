from datetime import datetime, timedelta
import pytz

def get_pacific_datetime():
    return datetime.now(pytz.timezone("US/Pacific"))

def get_pacific_date():
    return get_pacific_datetime().strftime("%Y-%m-%d")

def get_fantasy_week(start_date_str: str, current_dt=None) -> int:
    if current_dt is None:
        current_dt = get_pacific_datetime()
    
    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
    start_dt = pytz.timezone("US/Pacific").localize(start_dt)
    
    # Find the Monday 00:00 PT of the start week
    # start_dt.weekday(): 0=Monday, 1=Tuesday...
    start_monday = start_dt - timedelta(days=start_dt.weekday())
    start_monday = start_monday.replace(hour=0, minute=0, second=0, microsecond=0)
    delta = current_dt - start_monday
    week = (delta.days // 7) + 1
    return max(1, week)

def is_winter_time_pacific() -> bool:
    """
    本地極速判斷目前美西是否為冬令時間。
    1. 優先讀取 config 中的 IS_WINTER_TIME 覆蓋設定。
    2. 自動透過 pytz 本地檢測美西 DST 偏移量（0 網路耗時，微秒級）。
    """
    from src.config import load_config
    try:
        config = load_config()
        is_winter_override = config.get("IS_WINTER_TIME")
        if is_winter_override is not None:
            if isinstance(is_winter_override, str):
                return is_winter_override.lower() in ("true", "1", "yes")
            return bool(is_winter_override)
    except Exception:
        pass

    pacific_tz = pytz.timezone("US/Pacific")
    now_pacific = datetime.now(pacific_tz)
    # now_pacific.dst() 在夏令時不為 0，在冬令時為 0
    is_dst = now_pacific.dst().total_seconds() != 0
    return not is_dst

def get_target_date(is_offseason: bool = False, end_date: str = None, current_tw_dt=None) -> str:
    """
    計算美西目標日期 YYYY-MM-DD。
    台北時間 00:00 ~ cross_hour (夏令7點/冬令8點) -> 目標為 台北日期 - 2天。
    台北時間 cross_hour ~ 24:00 -> 目標為 台北日期 - 1天。
    """
    if is_offseason:
        return end_date or "2026-04-12"
        
    if current_tw_dt is None:
        tw_tz = pytz.timezone("Asia/Taipei")
        current_tw_dt = datetime.now(tw_tz)
        
    tw_date = current_tw_dt.date()
    tw_hour = current_tw_dt.hour
    
    # 依時令決定台北時間的跨日判定點 (冬令8點，夏令7點)
    cross_hour = 8 if is_winter_time_pacific() else 7
    
    if tw_hour >= cross_hour:
        target_dt = tw_date - timedelta(days=1)
    else:
        target_dt = tw_date - timedelta(days=2)
        
    return target_dt.strftime("%Y-%m-%d")

def is_stats_query_allowed(is_offseason: bool = False, target_date: str = None) -> tuple[bool, str]:
    """
    今日綜合戰績限制在美西打完比賽後才能查詢。
    優先透過 ESPN Scoreboard API 判斷，若無法判斷則降級退回時段阻擋：
    夏令台北時間 14:00 後允許，冬令台北時間 15:00 後允許。
    """
    if is_offseason:
        return True, ""
        
    if target_date is None:
        target_date = get_target_date(is_offseason=is_offseason)
        
    # 優先嘗試外部即時狀態監控
    espn_result = check_nba_game_status(target_date)
    if espn_result is not None:
        return espn_result
        
    # API 連線或解析異常，降級退回原有的靜態時段阻擋邏輯
    allow_hour = 15 if is_winter_time_pacific() else 14
    
    tw_tz = pytz.timezone("Asia/Taipei")
    tw_hour = datetime.now(tw_tz).hour
    
    if tw_hour < allow_hour:
        return False, f"請於 {allow_hour}:00 後再進行查詢。"
    return True, ""


def check_nba_game_status(date_str: str) -> tuple[bool, str] | None:
    """
    透過 ESPN Scoreboard API 即時檢查指定日期的 NBA 比賽狀態。
    參數:
        date_str: 格式為 YYYY-MM-DD 的日期字串
    回傳:
        tuple[bool, str]: (allowed, err_msg)
        None: 當 API 請求或解析發生異常時，回傳 None 以便上層進行時段降級備援。
    """
    import requests
    import logging

    try:
        espn_date = date_str.replace("-", "")
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={espn_date}"
        
        response = requests.get(url, timeout=3)
        response.raise_for_status()
        data = response.json()
        
        events = data.get("events", [])
        if not events:
            return True, ""
            
        n_pre = 0
        n_in = 0
        n_post = 0
        
        for event in events:
            status = event.get("status", {})
            status_type = status.get("type", {})
            state = status_type.get("state")  # 'pre', 'in', 'post'
            
            if state == "pre":
                n_pre += 1
            elif state == "in":
                n_in += 1
            elif state == "post":
                n_post += 1
                
        if n_in > 0:
            return False, "目前仍有比賽正在進行"
        elif n_pre > 0:
            if n_post > 0:
                return False, "今日比賽尚未全部結束，請在所有比賽結束後再進行查詢"
            else:
                return False, "今日比賽尚未開始"
        else:
            return True, ""
            
    except Exception as e:
        logging.warning(f"ESPN Scoreboard API 請求或解析失敗: {e}，將降級採用靜態時間阻擋規則。")
        return None

