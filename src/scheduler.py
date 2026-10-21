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
from src.utils.path_utils import BASE_DIR, DATA_DIR

TAIPEI_TZ = pytz.timezone("Asia/Taipei")


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


def trigger_daily_stats_push() -> int:
    """針對所有已綁定聯盟的聊天室觸發 AI Agent 網頁擷取與戰績推播任務。回傳觸發的任務數量。"""
    bindings = get_bound_chat_leagues()
    if not bindings:
        logging.warning("[SCHEDULER] 尚未有任何聊天室綁定聯盟 ID，跳過本次定時戰績推播。")
        return 0

    agent_script = os.path.join(BASE_DIR, "src", "web_agent_fetcher.py")
    triggered = 0
    for chat_id, league_id in bindings.items():
        env = os.environ.copy()
        env["LINE_REPLY_TO"] = str(chat_id)
        env["LEAGUE_ID"] = str(league_id)
        env["PYTHONPATH"] = BASE_DIR + os.pathsep + env.get("PYTHONPATH", "")
        logging.info(f"[SCHEDULER] 觸發每日 AI Agent 戰績更新任務: chat_id={chat_id}, league_id={league_id}")
        subprocess.Popen(
            [sys.executable, agent_script, "--push", "--league-id", str(league_id), "--reply-to", str(chat_id)],
            env=env
        )
        triggered += 1

    return triggered


def _scheduler_loop(target_time: str = "14:00", poll_interval: float = 20.0, stop_event: threading.Event = None):
    """背景常駐迴圈：每天到達指定台灣時間 (預設 14:00) 時執行一次推播任務。"""
    last_triggered_date = None
    logging.info(f"[SCHEDULER] 每日定時戰績 Agent 排程器已啟動，預定執行時間: 每日 {target_time} (Asia/Taipei)")

    while True:
        if stop_event and stop_event.is_set():
            break

        now_tw = datetime.now(TAIPEI_TZ)
        today_str = now_tw.strftime("%Y-%m-%d")
        current_hm = now_tw.strftime("%H:%M")

        if current_hm == target_time and last_triggered_date != today_str:
            last_triggered_date = today_str
            try:
                logging.info(f"[SCHEDULER] 時間到達 {today_str} {current_hm}，開始執行每日戰績抓取與推播...")
                trigger_daily_stats_push()
            except Exception as e:
                logging.error(f"[SCHEDULER] 執行每日排程時發生錯誤: {e}")

        if stop_event:
            if stop_event.wait(timeout=poll_interval):
                break
        else:
            time.sleep(poll_interval)


def start_daily_scheduler(target_time: str = None) -> threading.Thread:
    """啟動背景 Daemon 執行緒執行每日 14:00 排程，供 bot.py 串接呼叫。"""
    schedule_time = target_time or os.getenv("DAILY_PUSH_TIME", "14:00")
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
