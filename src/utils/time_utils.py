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


def yahoo_date_to_tw_date(yahoo_date_str: str) -> str:
    """將 Yahoo Fantasy 美西比賽日期字串 (YYYY-MM-DD) 轉換為對應的台灣日期 (加 1 天)。"""
    dt = datetime.strptime(yahoo_date_str, "%Y-%m-%d")
    return (dt + timedelta(days=1)).strftime("%Y-%m-%d")


def has_games_on_yahoo_date(sport: str, yahoo_date_str: str) -> bool | None:
    """
    透過 ESPN Scoreboard API 檢查指定美西日期 (YYYY-MM-DD) 是否有有效比賽。
    - 有有效比賽（非全部延期/取消）：回傳 True
    - 無任何比賽或全部延期/取消：回傳 False
    - API 連線或解析異常：回傳 None
    """
    tw_date_str = yahoo_date_to_tw_date(yahoo_date_str)
    info = fetch_daily_game_times_tw(sport, tw_date_str)
    if info is None:
        return None
    return bool(info.get("has_games", True))


def resolve_latest_active_tw_date(
    sport: str,
    candidate_tw_date: str,
    league_id: str = None,
    max_lookback_days: int = 7,
    prefer_existing_local: bool = False,
) -> str:
    """
    解析指定台灣日期 (candidate_tw_date) 對應的最新有效比賽日（台灣日期 YYYY-MM-DD）：
    1. 若 prefer_existing_local=True 且本地端已存在 candidate_tw_date 當天的戰績圖片或非全 0 daily JSON，直接採用 candidate_tw_date（0 網路耗時）。
    2. 否則透過 fetch_daily_game_times_tw 查詢 candidate_tw_date 是否有比賽：
       - 若當天有比賽（或 API 無法判定時未知），直接回傳 candidate_tw_date。
       - 若當天確定無比賽 (has_games is False)：
         * 優先從本地端該聯盟不大於 candidate_tw_date 的現有戰績圖檔 / 非全 0 daily JSON 中，挑選最後一天有數據的台灣日期。
         * 若本地端尚無歷史檔案，則透過 ESPN API 往前最多回推 max_lookback_days 天，找出最後一個有比賽的台灣日期。
         * 若回推期間皆無或 API 失敗，預設退回前一天 (candidate_tw_date - 1 天)。
    """
    import os
    import re
    import json

    def _collect_local_tw_dates(include_candidate: bool) -> set[str]:
        found: set[str] = set()
        if not league_id:
            return found
        try:
            from src.utils.path_utils import (
                get_league_image_dir,
                get_league_daily_dir,
            )

            is_mlb = (sport == "mlb")
            image_dir = get_league_image_dir(league_id)
            if os.path.exists(image_dir):
                try:
                    files = set(os.listdir(image_dir))
                except OSError:
                    files = set()
                for fn in files:
                    if is_mlb:
                        m = re.match(r"^(\d{4}-\d{2}-\d{2})_combined_hitter\.png$", fn)
                        if m and f"{m.group(1)}_combined_pitcher.png" in files:
                            d_val = m.group(1)
                            if (d_val <= candidate_tw_date) if include_candidate else (d_val < candidate_tw_date):
                                found.add(d_val)
                    else:
                        m = re.match(r"^(\d{4}-\d{2}-\d{2})_combined\.png$", fn)
                        if m:
                            d_val = m.group(1)
                            if (d_val <= candidate_tw_date) if include_candidate else (d_val < candidate_tw_date):
                                found.add(d_val)
                if include_candidate and candidate_tw_date not in found:
                    if is_mlb:
                        h_p = os.path.join(image_dir, f"{candidate_tw_date}_combined_hitter.png")
                        p_p = os.path.join(image_dir, f"{candidate_tw_date}_combined_pitcher.png")
                        if os.path.exists(h_p) and os.path.exists(p_p):
                            found.add(candidate_tw_date)
                    else:
                        c_p = os.path.join(image_dir, f"{candidate_tw_date}_combined.png")
                        if os.path.exists(c_p):
                            found.add(candidate_tw_date)

            daily_dir = get_league_daily_dir(league_id)
            if os.path.exists(daily_dir):
                try:
                    d_files = os.listdir(daily_dir)
                except OSError:
                    d_files = []
                for fn in d_files:
                    m = re.match(r"^(?:date_)?(\d{4}-\d{2}-\d{2})\.json$", fn)
                    if not m:
                        continue
                    fpath = os.path.join(daily_dir, fn)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        if not isinstance(data, dict) or not data.get("team_stats"):
                            continue
                        # 排除全 0 的無比賽日殘留檔
                        has_positive = False
                        for t in data.get("team_stats") or []:
                            st = (t.get("stats") or {}) if isinstance(t, dict) else {}
                            try:
                                if int(st.get("Today Player") or 0) > 0:
                                    has_positive = True
                                    break
                            except (ValueError, TypeError):
                                pass
                            for k, v in st.items():
                                if k in ("PTS", "REB", "AST", "ST", "STL", "BLK", "TO", "3PTM", "3PT", "3PM", "R", "H", "HR", "RBI", "W", "K"):
                                    try:
                                        if float(v or 0) > 0:
                                            has_positive = True
                                            break
                                    except (ValueError, TypeError):
                                        pass
                            if has_positive:
                                break
                        if not has_positive:
                            continue

                        raw_d = data.get("date") or m.group(1)
                        if fn.startswith("date_"):
                            tw_d = yahoo_date_to_tw_date(raw_d)
                        else:
                            tw_d = raw_d if raw_d <= candidate_tw_date else yahoo_date_to_tw_date(raw_d)
                        if (tw_d <= candidate_tw_date) if include_candidate else (tw_d < candidate_tw_date):
                            found.add(tw_d)
                    except Exception:
                        continue
        except Exception:
            pass
        return found

    if prefer_existing_local and league_id:
        local_with_cand = _collect_local_tw_dates(include_candidate=True)
        if candidate_tw_date in local_with_cand:
            return candidate_tw_date

    info = fetch_daily_game_times_tw(sport, candidate_tw_date)
    if info is None or info.get("has_games", True) is not False:
        return candidate_tw_date

    # 當天確定無比賽：優先檢查本地端已存在的最後一天有效數據 (< candidate_tw_date)
    local_prev = _collect_local_tw_dates(include_candidate=False)
    if local_prev:
        return max(local_prev)

    # 若本地無歷史檔案，透過 ESPN API 往前回推最近一個有比賽的台灣日期
    base_dt = datetime.strptime(candidate_tw_date, "%Y-%m-%d").date()
    for offset in range(1, max_lookback_days + 1):
        prev_tw_str = (base_dt - timedelta(days=offset)).strftime("%Y-%m-%d")
        prev_info = fetch_daily_game_times_tw(sport, prev_tw_str)
        if prev_info is None:
            return prev_tw_str
        if prev_info.get("has_games", True) is True:
            return prev_tw_str

    return (base_dt - timedelta(days=1)).strftime("%Y-%m-%d")

def get_stats_rule_date(current_tw_dt=None, cutoff_hm: str = "14:00") -> str:
    """
    依戰績規則計算目標日期 YYYY-MM-DD (以台北時間 Asia/Taipei 為準)：
    - cutoff_hm (預設 14:00) 之前輸入：回傳前一天 (台北日期 - 1 天)
    - cutoff_hm (預設 14:00) 及其之後輸入：回傳當天 (台北日期)
    例如：10/27 10:30 -> 10/26；10/27 14:01 -> 10/27
    """
    if current_tw_dt is None:
        tw_tz = pytz.timezone("Asia/Taipei")
        current_tw_dt = datetime.now(tw_tz)
    tw_date = current_tw_dt.date()
    current_hm = current_tw_dt.strftime("%H:%M")
    if current_hm < cutoff_hm:
        return (tw_date - timedelta(days=1)).strftime("%Y-%m-%d")
    return tw_date.strftime("%Y-%m-%d")


def _parse_espn_event_datetime_tw(date_val: str) -> datetime | None:
    """將 ESPN event['date'] (例如 '2026-10-27T02:30Z' 或 '2026-10-27T02:30:00Z') 轉為台北時間 datetime。"""
    if not date_val or not isinstance(date_val, str):
        return None
    s = date_val.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        return dt.astimezone(pytz.timezone("Asia/Taipei"))
    except Exception:
        for fmt in ("%Y-%m-%dT%H:%M%z", "%Y-%m-%dT%H:%M:%S%z"):
            try:
                dt = datetime.strptime(s, fmt)
                return dt.astimezone(pytz.timezone("Asia/Taipei"))
            except Exception:
                continue
    return None


def fetch_daily_game_times_tw(sport: str, tw_date_str: str) -> dict | None:
    """
    透過 ESPN Scoreboard API 查詢指定台灣日期 (對應美西比賽日 tw_date_str - 1 天) 的：
    - 第一場比賽開始時間 (first_game_time, HH:MM 台北時間)
    - 最後一場比賽開始時間 (last_game_time, HH:MM 台北時間)
    - 最後一場比賽開始時間 + 2 小時之開放查詢時間 (query_open_time, HH:MM)
    - 開放查詢時間前 5 分鐘之自動排程更新時間 (base_update_time, HH:MM)

    回傳 dict:
        {
            "date": tw_date_str,
            "yahoo_date": yahoo_date,
            "has_games": bool,
            "first_game_time": str | None,   # HH:MM
            "last_game_time": str | None,    # HH:MM
            "base_update_time": str,         # HH:MM (例如 12:55)
            "query_open_time": str,          # HH:MM (例如 13:00)
        }
    當 API 連線或解析異常時回傳 None，供上層降級回預設 13:55 / 14:00。
    """
    import requests
    import logging

    yahoo_date = tw_date_to_yahoo_date(tw_date_str)
    try:
        espn_date = yahoo_date.replace("-", "")
        espn_sport = "basketball/nba" if sport == "nba" else "baseball/mlb"
        url = f"https://site.api.espn.com/apis/site/v2/sports/{espn_sport}/scoreboard?dates={espn_date}"

        response = requests.get(url, timeout=3)
        response.raise_for_status()
        data = response.json()

        events = data.get("events", [])
        if not events:
            return {
                "date": tw_date_str,
                "yahoo_date": yahoo_date,
                "has_games": False,
                "first_game_time": None,
                "last_game_time": None,
                "base_update_time": "13:55",
                "query_open_time": "14:00",
            }

        start_dts_tw: list[datetime] = []
        for event in events:
            status = event.get("status", {})
            status_type = status.get("type", {})
            type_name = str(status_type.get("name") or "").upper()
            type_desc = str(status_type.get("description") or "").lower()
            if type_name in ("STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_CANCELLED") or type_desc in ("postponed", "canceled", "cancelled"):
                continue

            raw_date = event.get("date")
            if not raw_date:
                comps = event.get("competitions") or []
                if comps and isinstance(comps[0], dict):
                    raw_date = comps[0].get("date")
            dt_tw = _parse_espn_event_datetime_tw(raw_date)
            if dt_tw is not None:
                start_dts_tw.append(dt_tw)

        if not start_dts_tw:
            # 有 events 但全部延期/取消，或無可解析時間
            # 若為全部延期/取消則視為當日無有效比賽
            has_active = any(
                str(ev.get("status", {}).get("type", {}).get("name") or "").upper()
                not in ("STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_CANCELLED")
                and str(ev.get("status", {}).get("type", {}).get("description") or "").lower()
                not in ("postponed", "canceled", "cancelled")
                for ev in events
            )
            if not has_active:
                return {
                    "date": tw_date_str,
                    "yahoo_date": yahoo_date,
                    "has_games": False,
                    "first_game_time": None,
                    "last_game_time": None,
                    "base_update_time": "13:55",
                    "query_open_time": "14:00",
                }
            return None

        start_dts_tw.sort()
        first_dt = start_dts_tw[0]
        last_dt = start_dts_tw[-1]
        first_hm = first_dt.strftime("%H:%M")
        last_hm = last_dt.strftime("%H:%M")
        query_open_hm = add_minutes_to_hm(last_hm, 120)
        base_update_hm = add_minutes_to_hm(query_open_hm, -5)

        return {
            "date": tw_date_str,
            "yahoo_date": yahoo_date,
            "has_games": True,
            "first_game_time": first_hm,
            "last_game_time": last_hm,
            "base_update_time": base_update_hm,
            "query_open_time": query_open_hm,
        }
    except Exception as e:
        logging.warning(f"ESPN Scoreboard API ({sport}) 查詢比賽時間失敗: {e}，將降級採用預設 13:55/14:00 規則。")
        return None


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
