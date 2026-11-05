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

def get_today_tw_date(current_tw_dt=None) -> str:
    """獲取當前台北時間日期字串 YYYY-MM-DD。"""
    if current_tw_dt is None:
        tw_tz = pytz.timezone("Asia/Taipei")
        current_tw_dt = datetime.now(tw_tz)
    return current_tw_dt.strftime("%Y-%m-%d")

def tw_date_to_yahoo_date(tw_date_str: str) -> str:
    """將台灣日期字串 (YYYY-MM-DD) 轉換為對應的 Yahoo Fantasy 美西比賽日期 (減 1 天)。"""
    dt = datetime.strptime(tw_date_str, "%Y-%m-%d")
    return (dt - timedelta(days=1)).strftime("%Y-%m-%d")

def get_stats_rule_date(current_tw_dt=None) -> str:
    """
    依戰績規則計算目標日期 YYYY-MM-DD (以台北時間 Asia/Taipei 為準)：
    - 14:00 之前輸入：回傳前一天 (台北日期 - 1 天)
    - 14:00 及其之後輸入：回傳當天 (台北日期)
    例如：10/27 10:30 -> 10/26；10/27 14:01 -> 10/27
    """
    if current_tw_dt is None:
        tw_tz = pytz.timezone("Asia/Taipei")
        current_tw_dt = datetime.now(tw_tz)
    tw_date = current_tw_dt.date()
    if current_tw_dt.hour < 14:
        return (tw_date - timedelta(days=1)).strftime("%Y-%m-%d")
    return tw_date.strftime("%Y-%m-%d")


def hm_to_minutes(hm_str: str) -> int:
    """將 HH:MM 字串轉換為當日累計分鐘數 (0 ~ 1439)。"""
    parts = hm_str.strip().split(":")
    return int(parts[0]) * 60 + int(parts[1])


def minutes_to_hm(total_minutes: int) -> str:
    """將當日累計分鐘數轉換為 HH:MM 字串 (24 小時制)。"""
    total_minutes = total_minutes % (24 * 60)
    h = total_minutes // 60
    m = total_minutes % 60
    return f"{h:02d}:{m:02d}"


def add_minutes_to_hm(hm_str: str, minutes: int) -> str:
    """將 HH:MM 字串加上指定分鐘數並回傳新的 HH:MM 字串。"""
    return minutes_to_hm(hm_to_minutes(hm_str) + minutes)


def get_next_schedule_slot(current_hm: str, base_update_time: str = "13:55") -> tuple[str, str]:
    """
    根據當前時間 (HH:MM) 與基準更新時間 (預設 13:55)，計算延後半小時後的：
    (下次自動更新時間 next_update_time, 對應開放查詢時間 query_open_time)。
    規則：
    - 13:55 仍有比賽 -> 延至 14:25 更新，14:30 開放查詢
    - 14:25 仍有比賽 -> 延至 14:55 更新，15:00 開放查詢
    - 以此類推，每次延後 30 分鐘，開放查詢時間為更新時間 + 5 分鐘。
    """
    curr_min = hm_to_minutes(current_hm)
    base_min = hm_to_minutes(base_update_time)
    if curr_min < base_min:
        next_update_min = base_min
    else:
        slots_passed = ((curr_min - base_min) // 30) + 1
        next_update_min = base_min + 30 * slots_passed
    next_update_hm = minutes_to_hm(next_update_min)
    query_open_hm = minutes_to_hm(next_update_min + 5)
    return next_update_hm, query_open_hm

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

def is_stats_query_allowed(sport: str = "nba", is_offseason: bool = False, target_date: str = None) -> tuple[bool, str]:
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
    if sport == "nba":
        espn_result = check_nba_game_status(target_date)
    else:
        espn_result = check_game_status(sport, target_date)
    if espn_result is not None:
        return espn_result
        
    # API 連線或解析異常，降級退回原有的靜態時段阻擋邏輯
    allow_hour = 15 if is_winter_time_pacific() else 14
    
    tw_tz = pytz.timezone("Asia/Taipei")
    tw_hour = datetime.now(tw_tz).hour
    
    if tw_hour < allow_hour:
        return False, f"請於 {allow_hour}:00 後再進行查詢。"
    return True, ""


def check_game_status(sport: str, date_str: str) -> tuple[bool, str] | None:
    """
    透過 ESPN Scoreboard API 即時檢查指定日期的 NBA 或 MLB 比賽狀態。
    參數:
        sport: 'nba' 或 'mlb'
        date_str: 格式為 YYYY-MM-DD 的日期字串
    回傳:
        tuple[bool, str]: (allowed, err_msg)
        None: 當 API 請求或解析發生異常時，回傳 None 以便上層進行時段降級備援。
    """
    import requests
    import logging

    try:
        espn_date = date_str.replace("-", "")
        # 動態決定 ESPN API 的體育項目路徑
        espn_sport = "basketball/nba" if sport == "nba" else "baseball/mlb"
        url = f"https://site.api.espn.com/apis/site/v2/sports/{espn_sport}/scoreboard?dates={espn_date}"
        
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
            type_name = str(status_type.get("name") or "").upper()
            type_desc = str(status_type.get("description") or "").lower()
            if type_name in ("STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_CANCELLED") or type_desc in ("postponed", "canceled", "cancelled"):
                n_post += 1
                continue
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
        logging.warning(f"ESPN Scoreboard API ({sport}) 請求或解析失敗: {e}，將降級採用靜態時間阻擋規則。")
        return None


def check_nba_game_status(date_str: str) -> tuple[bool, str] | None:
    """向後相容舊測試用之轉接函數"""
    return check_game_status("nba", date_str)


def is_game_day(sport: str = "nba", is_offseason: bool = False, target_date: str = None) -> tuple[bool, str]:
    if sport not in ("nba", "mlb"):
        return True, ""
    return is_stats_query_allowed(sport=sport, is_offseason=is_offseason, target_date=target_date)


def check_game_day(date_str: str = None, sport: str = "nba") -> tuple[bool, str] | None:
    if sport not in ("nba", "mlb"):
        return True, ""
    if date_str is None:
        date_str = get_target_date()
    return check_game_status(sport, date_str)
