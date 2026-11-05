import os
import sys

# 確保專案根目錄在 sys.path 中，避免以腳本直接執行時找不到 src 模組
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import json
import time
import logging
import threading
import subprocess
import argparse
from datetime import datetime
import pytz
from src.config import load_config
from src.utils.path_utils import BASE_DIR, DATA_DIR, parse_league_id
from src.utils.time_utils import (
    add_minutes_to_hm,
    get_next_schedule_slot,
    tw_date_to_yahoo_date,
    check_game_status,
)

TAIPEI_TZ = pytz.timezone("Asia/Taipei")
_MEMORY_SCHEDULE_STATE: dict[str, dict] = {}


def get_schedule_state_path() -> str:
    """回傳當日排程延後狀態檔路徑。"""
    return os.path.join(DATA_DIR, "security", "daily_schedule_state.json")


def clear_daily_schedule_state() -> None:
    """清除記憶體與磁碟中的當日排程狀態（供測試或重置使用）。"""
    _MEMORY_SCHEDULE_STATE.clear()
    state_path = get_schedule_state_path()
    if os.path.exists(state_path):
        try:
            os.remove(state_path)
        except Exception:
            pass


def get_daily_schedule_state(date_str: str) -> dict | None:
    """讀取指定台灣日期 (YYYY-MM-DD) 的排程與查詢開放時間狀態。"""
    state_path = get_schedule_state_path()
    try:
        if os.path.exists(state_path):
            with open(state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data.get("date") == date_str:
                    _MEMORY_SCHEDULE_STATE[date_str] = data
                    return dict(data)
    except Exception:
        pass

    mem = _MEMORY_SCHEDULE_STATE.get(date_str)
    if mem and mem.get("date") == date_str:
        return dict(mem)
    return None


def save_daily_schedule_state(
    date_str: str,
    next_update_time: str,
    query_open_time: str,
    games_in_progress: bool,
    completed: bool = False
) -> dict:
    """儲存指定台灣日期的自動更新時間與 #戰績 開放查詢時間狀態。"""
    state = {
        "date": date_str,
        "next_update_time": next_update_time,
        "query_open_time": query_open_time,
        "games_in_progress": bool(games_in_progress),
        "completed": bool(completed),
    }
    _MEMORY_SCHEDULE_STATE[date_str] = dict(state)
    state_path = get_schedule_state_path()
    try:
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.debug(f"[SCHEDULER] 寫入 daily_schedule_state.json 失敗: {e}")
    return state


def postpone_daily_schedule(
    date_str: str,
    current_hm: str = None,
    base_update_time: str = "13:55"
) -> dict:
    """
    因比賽仍在進行中，將自動更新時間延後半小時 (例如 13:55 -> 14:25 -> 14:55)，
    並將開放查詢時間同步設為下次更新時間 + 5 分鐘 (例如 14:00 -> 14:30 -> 15:00)。
    """
    if not current_hm:
        current_hm = datetime.now(TAIPEI_TZ).strftime("%H:%M")
    next_update_time, query_open_time = get_next_schedule_slot(current_hm, base_update_time=base_update_time)
    return save_daily_schedule_state(
        date_str=date_str,
        next_update_time=next_update_time,
        query_open_time=query_open_time,
        games_in_progress=True,
        completed=False
    )


def mark_daily_schedule_completed(date_str: str, update_time: str, query_open_time: str = None) -> dict:
    """標記當日自動更新已啟動/完成，並記錄該梯次對應的開放查詢時間 (update_time + 5 分鐘)。"""
    open_time = query_open_time or add_minutes_to_hm(update_time, 5)
    return save_daily_schedule_state(
        date_str=date_str,
        next_update_time=update_time,
        query_open_time=open_time,
        games_in_progress=False,
        completed=True
    )


def are_games_still_in_progress(tw_date_str: str = None, sport: str = None) -> bool:
    """
    檢查指定台灣日期對應之美西比賽日是否仍有比賽正在進行或尚未結束。
    回傳 True 代表仍有比賽進行中（需延後更新）；False 代表比賽已全部結束或無賽事。
    """
    if not tw_date_str:
        tw_date_str = datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d")
    yahoo_date = tw_date_to_yahoo_date(tw_date_str)

    if sport:
        sports_to_check = [sport]
    else:
        bindings = get_bound_chat_leagues()
        sports_set = set()
        for lid in bindings.values():
            sp, _ = parse_league_id(lid)
            if sp in ("nba", "mlb"):
                sports_set.add(sp)
        sports_to_check = sorted(sports_set) if sports_set else ["nba"]

    for sp in sports_to_check:
        res = check_game_status(sp, yahoo_date)
        if res is not None:
            allowed, _ = res
            if not allowed:
                return True
    return False


def get_bound_chat_leagues() -> dict[str, str]:
    """讀取所有已綁定的 (chat_id -> league_id) 映射表。"""
    mapping_file = os.path.join(DATA_DIR, "security", "chat_league_mapping.json")
    mapping = {}
    if os.path.exists(mapping_file):
        try:
            with open(mapping_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    mapping = {str(k): str(v) for k, v in data.items() if k and v}
        except Exception as e:
            logging.error(f"[SCHEDULER] 讀取 chat_league_mapping.json 失敗: {e}")

    if not mapping:
        config = load_config()
        fallback_chat = os.getenv("LINE_REPLY_TO")
        fallback_league = config.get("LEAGUE_ID")
        if fallback_chat and fallback_league:
            mapping[str(fallback_chat)] = str(fallback_league)

    return mapping


def trigger_daily_stats_push(target_date: str = None) -> int:
    """針對所有已綁定聯盟的聊天室觸發 AI Agent 網頁擷取與戰績推播任務。回傳觸發的任務數量。"""
    bindings = get_bound_chat_leagues()
    if not bindings:
        logging.warning("[SCHEDULER] 尚未有任何聊天室綁定聯盟 ID，跳過本次定時戰績推播。")
        return 0

    if not target_date:
        now_tw = datetime.now(TAIPEI_TZ)
        target_date = now_tw.strftime("%Y-%m-%d")

    agent_script = os.path.join(BASE_DIR, "src", "web_agent_fetcher.py")
    triggered = 0
    for chat_id, league_id in bindings.items():
        env = os.environ.copy()
        env["LINE_REPLY_TO"] = str(chat_id)
        env["LEAGUE_ID"] = str(league_id)
        env["PYTHONPATH"] = BASE_DIR + os.pathsep + env.get("PYTHONPATH", "")
        logging.info(f"[SCHEDULER] 觸發每日 AI Agent 戰績快取更新任務 ({target_date}): chat_id={chat_id}, league_id={league_id}")
        subprocess.Popen(
            [sys.executable, agent_script, "--fetch-only", "--league-id", str(league_id), "--reply-to", str(chat_id), "--date", str(target_date)],
            env=env
        )
        triggered += 1

    return triggered


def _scheduler_loop(target_time: str = "13:55", poll_interval: float = 20.0, stop_event: threading.Event = None):
    """
    背景常駐迴圈：每天到達指定台灣時間 (預設 13:55) 時執行一次推播任務。
    若當下仍有比賽正在進行，則自動延後半小時 (例如 13:55 -> 14:25 -> 14:55...) 再嘗試更新，
    並同步將當日開放查詢時間順延半小時 (例如 14:00 -> 14:30 -> 15:00...)。
    """
    active_date = None
    active_target_time = target_time
    completed_date = None
    last_attempted_slot = None
    logging.info(f"[SCHEDULER] 每日定時戰績 Agent 排程器已啟動，預定執行時間: 每日 {target_time} (Asia/Taipei)")

    while True:
        if stop_event and stop_event.is_set():
            break

        now_tw = datetime.now(TAIPEI_TZ)
        today_str = now_tw.strftime("%Y-%m-%d")
        current_hm = now_tw.strftime("%H:%M")

        if active_date != today_str:
            active_date = today_str
            active_target_time = target_time
            completed_date = None
            last_attempted_slot = None

        state = get_daily_schedule_state(today_str)
        if state and not state.get("completed") and state.get("next_update_time"):
            if state["next_update_time"] > active_target_time:
                active_target_time = state["next_update_time"]
                completed_date = None

        if (
            completed_date != today_str
            and current_hm == active_target_time
            and last_attempted_slot != (today_str, active_target_time)
        ):
            last_attempted_slot = (today_str, active_target_time)
            try:
                if are_games_still_in_progress(today_str):
                    postponed = postpone_daily_schedule(
                        today_str,
                        current_hm=active_target_time,
                        base_update_time=target_time
                    )
                    active_target_time = postponed["next_update_time"]
                    logging.info(
                        f"[SCHEDULER] 時間 {today_str} {current_hm} 檢測到仍有比賽正在進行，"
                        f"自動更新延後半小時至 {active_target_time}（開放查詢時間順延至 {postponed['query_open_time']}）。"
                    )
                else:
                    if active_target_time != target_time or state is not None:
                        mark_daily_schedule_completed(today_str, update_time=active_target_time)
                    completed_date = today_str
                    logging.info(f"[SCHEDULER] 時間到達 {today_str} {current_hm}，開始執行每日戰績抓取與推播...")
                    trigger_daily_stats_push(today_str)
            except Exception as e:
                logging.error(f"[SCHEDULER] 執行每日排程時發生錯誤: {e}")

        if stop_event:
            if stop_event.wait(timeout=poll_interval):
                break
        else:
            time.sleep(poll_interval)


def start_daily_scheduler(target_time: str = None) -> threading.Thread:
    """啟動背景 Daemon 執行緒執行每日 13:55 排程，供 bot.py 串接呼叫。"""
    schedule_time = target_time or os.getenv("DAILY_PUSH_TIME", "13:55")
    thread = threading.Thread(
        target=_scheduler_loop,
        kwargs={"target_time": schedule_time},
        daemon=True,
        name="DailyStatsAgentScheduler"
    )
    thread.start()
    return thread


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    parser = argparse.ArgumentParser(description="每日 14:00 Yahoo Fantasy AI Agent 戰績推播排程器")
    parser.add_argument("--now", action="store_true", help="立即觸發一次戰績抓取與推播")
    parser.add_argument("--time", type=str, default=os.getenv("DAILY_PUSH_TIME", "14:00"), help="每日推播時間 (預設 14:00)")
    args = parser.parse_args()

    if args.now:
        trigger_daily_stats_push()
    else:
        _scheduler_loop(target_time=args.time)
