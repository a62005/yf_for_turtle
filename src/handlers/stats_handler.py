import re
import os
import sys
import json
import logging
from datetime import datetime, timedelta
import pytz
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, ImageMessage
from .base_handler import BaseHandler

# Required project imports
from src.config import load_config
from src.utils.cache_utils import load_league_metadata
from src.utils.time_utils import (
    get_stats_rule_date,
    tw_date_to_yahoo_date,
    get_fantasy_week,
    resolve_latest_active_tw_date,
)
from src.utils.path_utils import (
    get_league_dir,
    get_league_image_dir,
    get_league_daily_dir,
    get_league_weekly_dir,
    parse_league_id,
)
from src.scheduler import (
    get_daily_schedule_state,
    ensure_daily_game_schedule,
    postpone_daily_schedule,
    mark_daily_schedule_completed,
    are_games_still_in_progress,
)


def _get_now_tw() -> datetime:
    return datetime.now(pytz.timezone("Asia/Taipei"))


def _yahoo_date_to_tw_date(yahoo_date_str: str) -> str:
    dt = datetime.strptime(yahoo_date_str, "%Y-%m-%d")
    return (dt + timedelta(days=1)).strftime("%Y-%m-%d")


def _split_mlb_stats(processed_list):
    hitter_list = [c for c in processed_list if c.get("is_common") or not c.get("is_pitcher")]
    pitcher_list = [c for c in processed_list if c.get("is_common") or c.get("is_pitcher")]
    return hitter_list, pitcher_list


class StatsHandler(BaseHandler):
    """
    戰績查詢處理器：
    支援以下指令（僅限當季本地現有數據）：
    - #戰績：查詢當天的聯賽整體戰績（依當日比賽時間動態提供前一日或當日最新戰績）
    - #戰績昨天 / #戰績 昨天：查詢昨天的聯賽整體戰績
    - #戰績上週 / #戰績 上週：查詢上週的聯賽整體戰績
    - #戰績W<週數> / #戰績 W<週數>：查詢特定週數的戰績
    - #戰績<YYYYMMDD> / #戰績 <YYYYMMDD>：查詢特定日期的戰績
    若為歷史查詢（昨天 / 上週 / 特定週數 / 特定日期）且非當季或本地無現有數據，則靜默不回應。
    """

    def __init__(self):
        self.combined_pattern = re.compile(r"^#戰績$")
        self.yesterday_pattern = re.compile(r"^#戰績\s*昨天$")
        self.last_week_pattern = re.compile(r"^#戰績\s*上週$")
        self.specific_week_pattern = re.compile(r"^#戰績\s*W(\d+)$", re.IGNORECASE)
        self.specific_date_pattern = re.compile(r"^#戰績\s*(\d{8}|\d{4}-\d{2}-\d{2})$")

    @property
    def instruction_desc(self) -> str:
        return """
- #戰績：查詢當天的聯賽整體戰績（依當日比賽時間動態提供前一日或當日最新戰績）。
- #戰績昨天：查詢昨天的聯賽整體戰績。
- #戰績上週：查詢上週的聯賽整體戰績。
- #戰績W<週數>：查詢當季特定週數的戰績（例如：#戰績W5 或 #戰績 W5）。
- #戰績<年月日>：查詢當季特定日期的戰績（例如：#戰績20261120 或 #戰績 20261120）。
        """

    def parse_command(self, user_text: str) -> tuple[str | None, str | int | None]:
        text = user_text.strip()
        if self.combined_pattern.match(text):
            return "combined", None
        if self.yesterday_pattern.match(text):
            return "yesterday", None
        if self.last_week_pattern.match(text):
            return "last_week", None

        m_week = self.specific_week_pattern.match(text)
        if m_week:
            return "specific_week", int(m_week.group(1))

        m_date = self.specific_date_pattern.match(text)
        if m_date:
            raw_date = m_date.group(1)
            if "-" in raw_date:
                try:
                    datetime.strptime(raw_date, "%Y-%m-%d")
                    return "specific_date", raw_date
                except ValueError:
                    return None, None
            else:
                formatted = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
                try:
                    datetime.strptime(formatted, "%Y-%m-%d")
                    return "specific_date", formatted
                except ValueError:
                    return None, None

        return None, None

    def can_handle(self, user_text: str) -> bool:
        cmd_type, _ = self.parse_command(user_text)
        return cmd_type is not None

    def _resolve_target_date_and_notice(
        self,
        now_tw: datetime,
        sport: str,
        league_id: str = None,
    ) -> tuple[str, str | None, bool, dict]:
        """
        根據當前台北時間與當日賽程狀態，決定：
        (target_date, notice_prefix, is_today_query, schedule_state)
        若目標日期或回退的前一日當天無比賽，自動往前回推至最後一天有比賽的日期。
        """
        today_str = now_tw.strftime("%Y-%m-%d")
        yesterday_str = (now_tw.date() - timedelta(days=1)).strftime("%Y-%m-%d")
        current_hm = now_tw.strftime("%H:%M")

        def _fallback_prev_active() -> str:
            return resolve_latest_active_tw_date(
                sport,
                yesterday_str,
                league_id=league_id,
                prefer_existing_local=True,
            )

        state = ensure_daily_game_schedule(today_str, sport=sport)
        has_games = state.get("has_games", True)
        if has_games is False:
            return _fallback_prev_active(), None, False, state

        first_hm = state.get("first_game_time")
        last_hm = state.get("last_game_time")
        base_update_hm = state.get("base_update_time") or "13:55"
        next_update_hm = state.get("next_update_time") or base_update_hm
        query_open_hm = state.get("query_open_time") or "14:00"

        # 若處於延後狀態且已抵達或超過下次排程檢查時間，動態刷新比賽是否仍在進行
        if state.get("games_in_progress") and current_hm >= next_update_hm:
            if are_games_still_in_progress(today_str, sport=sport):
                state = postpone_daily_schedule(
                    today_str,
                    current_hm=current_hm,
                    base_update_time=base_update_hm
                )
            else:
                state = mark_daily_schedule_completed(
                    today_str,
                    update_time=next_update_hm
                )
            query_open_hm = state.get("query_open_time") or query_open_hm

        # 情況 A：成功取得當日首場與末場比賽時間
        if first_hm and last_hm:
            if current_hm < first_hm:
                # 跨日後 ～ 第一場比賽開始前：直接回傳前一天（或最後一天比賽日）戰績，不帶提示
                return _fallback_prev_active(), None, False, state

            if current_hm < last_hm:
                # 第一場比賽開始 ～ 最後一場比賽開始之間：告知今日比賽尚未完全結束，並回傳前一天戰績
                return _fallback_prev_active(), "今日比賽尚未完全結束", False, state

            # 已達或超過最後一場比賽開始時間 (current_hm >= last_hm)
            if state.get("games_in_progress") or current_hm < query_open_hm:
                notice = f"因稍早或當前仍有比賽正在進行，請於{query_open_hm}後再次查詢"
                return _fallback_prev_active(), notice, False, state

            # 已達開放查詢時間 (最後一場 + 2HRS 或順延後開放時間)
            return today_str, None, True, state

        # 情況 B：ESPN API 失敗降級 (無 first_hm / last_hm，沿用 query_open_hm 預設 14:00 切日)
        rule_date = get_stats_rule_date(now_tw)
        if rule_date != today_str:
            return resolve_latest_active_tw_date(
                sport,
                rule_date,
                league_id=league_id,
                prefer_existing_local=True,
            ), None, False, state

        if state.get("games_in_progress") or current_hm < query_open_hm:
            notice = f"因稍早或當前仍有比賽正在進行，請於{query_open_hm}後再次查詢"
            return _fallback_prev_active(), notice, False, state

        return rule_date, None, True, state

    def _get_current_season_bounds(
        self,
        league_id: str,
        config: dict,
        meta: dict,
        now_tw: datetime
    ) -> tuple[str | None, str | None, int | None, bool]:
        """
        計算「當季」的美西開季日期 (season_start_yahoo)、美西結束日期 (season_end_yahoo)、
        總週數 (end_week)，以及 metadata.json 是否為過期的上一季資料 (is_stale_meta)。
        """
        meta = meta or {}
        meta_start = meta.get("start_date")
        meta_end = meta.get("end_date")
        meta_end_week = meta.get("end_week")

        next_season_raw = (
            config.get("NEXT_SEASON_START_DATE")
            or config.get(" next_season_start_date")
            or meta.get("next_season_start_date")
        )
        if not next_season_raw:
            settings_path = os.path.join(get_league_dir(league_id), "settings.json")
            if os.path.exists(settings_path):
                try:
                    with open(settings_path, "r", encoding="utf-8") as f:
                        s_data = json.load(f)
                    next_season_raw = s_data.get("NEXT_SEASON_START_DATE") or s_data.get("next_season_start_date")
                except Exception:
                    pass

        next_season_tw = str(next_season_raw).strip()[:10] if next_season_raw else None
        today_tw_str = now_tw.strftime("%Y-%m-%d")
        today_yahoo_str = tw_date_to_yahoo_date(today_tw_str)

        # 收集本地現有檔案日期（轉為美西 yahoo_date 基準）
        local_yahoo_dates = set()
        daily_dir = get_league_daily_dir(league_id)
        if os.path.exists(daily_dir):
            for fn in os.listdir(daily_dir):
                m = re.match(r"^(?:date_)?(\d{4}-\d{2}-\d{2})\.json$", fn)
                if m:
                    local_yahoo_dates.add(m.group(1))
        weekly_dir = get_league_weekly_dir(league_id)
        if os.path.exists(weekly_dir):
            for fn in os.listdir(weekly_dir):
                m = re.match(r"^(?:date_)?(\d{4}-\d{2}-\d{2})_weekly\.json$", fn)
                if m:
                    local_yahoo_dates.add(m.group(1))
        image_dir = get_league_image_dir(league_id)
        if os.path.exists(image_dir):
            for fn in os.listdir(image_dir):
                m = re.match(r"^(\d{4}-\d{2}-\d{2})_combined(?:_hitter|_pitcher)?\.png$", fn)
                if m:
                    try:
                        local_yahoo_dates.add(tw_date_to_yahoo_date(m.group(1)))
                    except Exception:
                        pass

        # 判斷是否已經進入新球季（metadata.json 停留在上一季）
        is_stale_meta = False
        if meta_end:
            has_newer_local = any(d > meta_end for d in local_yahoo_dates)
            has_newer_next = bool(next_season_tw and next_season_tw > meta_end and today_tw_str >= next_season_tw)
            if has_newer_local or has_newer_next or today_yahoo_str > meta_end:
                try:
                    days_past = (
                        datetime.strptime(today_yahoo_str, "%Y-%m-%d")
                        - datetime.strptime(meta_end, "%Y-%m-%d")
                    ).days
                except Exception:
                    days_past = 0
                if has_newer_local or has_newer_next or days_past > 60:
                    is_stale_meta = True

        if is_stale_meta:
            newer_local = sorted(d for d in local_yahoo_dates if d > meta_end)
            if next_season_tw and next_season_tw > meta_end:
                try:
                    ns_yahoo = tw_date_to_yahoo_date(next_season_tw)
                except Exception:
                    ns_yahoo = next_season_tw
                if newer_local:
                    season_start_yahoo = min(ns_yahoo, newer_local[0])
                else:
                    season_start_yahoo = ns_yahoo
            elif newer_local:
                season_start_yahoo = newer_local[0]
            else:
                # 尚無新球季設定與本地檔案，推估當年 10 月 1 日為新球季起點
                season_start_yahoo = f"{now_tw.year}-10-01"
            return season_start_yahoo, None, None, True

        # metadata 為當季或未設定 end_date
        season_start_yahoo = meta_start or config.get("SEASON_START_DATE")
        if not season_start_yahoo and next_season_tw:
            try:
                season_start_yahoo = tw_date_to_yahoo_date(next_season_tw)
            except Exception:
                season_start_yahoo = next_season_tw
        if not season_start_yahoo and local_yahoo_dates:
            season_start_yahoo = min(local_yahoo_dates)

        end_week_val = None
        if meta_end_week is not None:
            try:
                end_week_val = int(meta_end_week)
            except (ValueError, TypeError):
                end_week_val = None

        return season_start_yahoo, meta_end, end_week_val, False

    def _is_tw_date_in_current_season(
        self,
        tw_date_str: str,
        now_tw: datetime,
        season_start_yahoo: str | None,
        season_end_yahoo: str | None
    ) -> bool:
        """檢查台灣日期 (YYYY-MM-DD) 是否在當季有效範圍內且不超過今天。"""
        today_tw_str = now_tw.strftime("%Y-%m-%d")
        if tw_date_str > today_tw_str:
            return False

        try:
            yahoo_date_str = tw_date_to_yahoo_date(tw_date_str)
        except Exception:
            return False

        if season_start_yahoo:
            # 容許 tw_date_str 本身 >= season_start_yahoo（以防測試直接以台灣日期作為 start_date）
            if yahoo_date_str < season_start_yahoo and tw_date_str < season_start_yahoo:
                return False

        if season_end_yahoo:
            try:
                end_tw_str = _yahoo_date_to_tw_date(season_end_yahoo)
            except Exception:
                end_tw_str = season_end_yahoo
            if yahoo_date_str > season_end_yahoo and tw_date_str > end_tw_str:
                return False

        return True

    def _resolve_week_for_yahoo_date(
        self,
        yahoo_date_str: str,
        payload: dict | None,
        season_start_yahoo: str | None,
        end_week: int | None,
        meta: dict,
        is_stale_meta: bool
    ) -> int | None:
        if isinstance(payload, dict) and payload.get("week") is not None:
            try:
                return int(payload["week"])
            except (ValueError, TypeError):
                pass

        if not is_stale_meta and isinstance(meta, dict):
            date_to_week = meta.get("date_to_week") or {}
            if yahoo_date_str in date_to_week:
                try:
                    return int(date_to_week[yahoo_date_str])
                except (ValueError, TypeError):
                    pass
            try:
                tw_d = _yahoo_date_to_tw_date(yahoo_date_str)
                if tw_d in date_to_week:
                    return int(date_to_week[tw_d])
            except Exception:
                pass

        if season_start_yahoo and yahoo_date_str:
            try:
                target_dt = pytz.timezone("US/Pacific").localize(
                    datetime.strptime(yahoo_date_str, "%Y-%m-%d")
                )
                w = get_fantasy_week(season_start_yahoo, target_dt)
                if end_week and w > end_week:
                    w = end_week
                return max(1, int(w))
            except Exception:
                pass
        return None

    def _collect_current_season_entries(
        self,
        league_id: str,
        sport: str,
        now_tw: datetime,
        season_start_yahoo: str | None,
        season_end_yahoo: str | None,
        end_week: int | None,
        meta: dict,
        is_stale_meta: bool
    ) -> list[dict]:
        """
        掃描本地現有的 image / daily / weekly 資料，回傳所有屬於「當季」的可用台灣日期清單（由舊到新排序）。
        每個元素為: {"tw_date": str, "yahoo_date": str, "week": int | None}
        """
        is_mlb = (sport == "mlb")
        image_dir = get_league_image_dir(league_id)
        daily_dir = get_league_daily_dir(league_id)
        weekly_dir = get_league_weekly_dir(league_id)

        candidate_tw_dates: set[str] = set()
        payload_by_yahoo_date: dict[str, dict] = {}

        # 1. 掃描 image 目錄中的現有戰績圖
        if os.path.exists(image_dir):
            files = set(os.listdir(image_dir))
            for fn in files:
                if is_mlb:
                    m = re.match(r"^(\d{4}-\d{2}-\d{2})_combined_hitter\.png$", fn)
                    if m and f"{m.group(1)}_combined_pitcher.png" in files:
                        candidate_tw_dates.add(m.group(1))
                else:
                    m = re.match(r"^(\d{4}-\d{2}-\d{2})_combined\.png$", fn)
                    if m:
                        candidate_tw_dates.add(m.group(1))

        # 2. 掃描 daily 目錄中的 JSON
        if os.path.exists(daily_dir):
            for fn in os.listdir(daily_dir):
                m = re.match(r"^(?:date_)?(\d{4}-\d{2}-\d{2})\.json$", fn)
                if not m:
                    continue
                y_date = m.group(1)
                fpath = os.path.join(daily_dir, fn)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict) and data.get("team_stats"):
                        payload_by_yahoo_date.setdefault(y_date, data)
                        candidate_tw_dates.add(_yahoo_date_to_tw_date(y_date))
                except Exception:
                    continue

        # 3. 掃描 weekly 目錄中的 JSON
        if os.path.exists(weekly_dir):
            for fn in os.listdir(weekly_dir):
                m = re.match(r"^(?:date_)?(\d{4}-\d{2}-\d{2})_weekly\.json$", fn)
                if not m:
                    continue
                y_date = m.group(1)
                fpath = os.path.join(weekly_dir, fn)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict) and data.get("team_stats"):
                        payload_by_yahoo_date.setdefault(y_date, data)
                        candidate_tw_dates.add(_yahoo_date_to_tw_date(y_date))
                except Exception:
                    continue

        entries = []
        for tw_d in sorted(candidate_tw_dates):
            if not self._is_tw_date_in_current_season(tw_d, now_tw, season_start_yahoo, season_end_yahoo):
                continue
            y_d = tw_date_to_yahoo_date(tw_d)
            payload = payload_by_yahoo_date.get(y_d) or payload_by_yahoo_date.get(tw_d)
            w = self._resolve_week_for_yahoo_date(
                yahoo_date_str=y_d,
                payload=payload,
                season_start_yahoo=season_start_yahoo,
                end_week=end_week,
                meta=meta,
                is_stale_meta=is_stale_meta,
            )
            entries.append({
                "tw_date": tw_d,
                "yahoo_date": y_d,
                "week": w,
            })

        return entries

    def _load_local_stats_pair(self, league_id: str, target_tw_date: str) -> tuple[dict | None, dict | None]:
        """從本地端 daily/ 與 weekly/ 讀取指定台灣日期對應的 JSON 數據（絕不呼叫網路爬蟲）。"""
        daily_dir = get_league_daily_dir(league_id)
        weekly_dir = get_league_weekly_dir(league_id)
        yahoo_date = tw_date_to_yahoo_date(target_tw_date)

        daily_stats = None
        if os.path.exists(daily_dir):
            for fname in (
                f"date_{yahoo_date}.json",
                f"{yahoo_date}.json",
                f"date_{target_tw_date}.json",
                f"{target_tw_date}.json",
            ):
                fpath = os.path.join(daily_dir, fname)
                if os.path.exists(fpath):
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        if isinstance(data, dict) and data.get("team_stats"):
                            daily_stats = data
                            break
                    except Exception:
                        continue

        weekly_stats = None
        if os.path.exists(weekly_dir):
            for fname in (
                f"date_{yahoo_date}_weekly.json",
                f"{yahoo_date}_weekly.json",
                f"date_{target_tw_date}_weekly.json",
                f"{target_tw_date}_weekly.json",
            ):
                fpath = os.path.join(weekly_dir, fname)
                if os.path.exists(fpath):
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        if isinstance(data, dict) and data.get("team_stats"):
                            weekly_stats = data
                            break
                    except Exception:
                        continue

            if weekly_stats is None and isinstance(daily_stats, dict) and daily_stats.get("week"):
                w_fpath = os.path.join(weekly_dir, f"week_{daily_stats['week']}.json")
                if os.path.exists(w_fpath):
                    try:
                        with open(w_fpath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        if isinstance(data, dict) and data.get("team_stats"):
                            weekly_stats = data
                    except Exception:
                        pass

        return daily_stats, weekly_stats

    def _check_and_generate_images(
        self,
        league_id: str,
        sport: str,
        image_dir: str,
        target_date: str,
        allow_remote_fetch: bool = False
    ) -> tuple[bool, list[str]]:
        """
        檢查指定 target_date 的戰績圖片是否存在；
        若不存在，優先嘗試從本地現有 daily/weekly JSON 渲染生成圖檔；
        僅當 allow_remote_fetch=True 且本地也無 JSON 時，才啟動 WebAgentFetcher 現場抓取。
        """
        is_mlb = (sport == "mlb")
        if is_mlb:
            hitter_name = f"{target_date}_combined_hitter.png"
            pitcher_name = f"{target_date}_combined_pitcher.png"
            h_path = os.path.join(image_dir, hitter_name)
            p_path = os.path.join(image_dir, pitcher_name)
            filenames = [hitter_name, pitcher_name]
            image_exists = os.path.exists(h_path) and os.path.exists(p_path)
        else:
            img_filename = f"{target_date}_combined.png"
            img_path = os.path.join(image_dir, img_filename)
            filenames = [img_filename]
            image_exists = os.path.exists(img_path)

        if image_exists:
            return True, filenames

        # 1. 優先嘗試使用本地現有的 daily + weekly JSON 渲染圖片
        daily_stats, weekly_stats = self._load_local_stats_pair(league_id, target_date)
        if daily_stats and weekly_stats:
            logging.info(f"[STATS] 本地已有 {target_date} 的 JSON 數據，直接從本地數據渲染戰績圖片...")
            try:
                from src.visualizer.processor import process_stats_for_visual
                from src.visualizer.renderer import render_stats_html
                from src.visualizer.capturer import capture_html_to_png

                daily_processed = process_stats_for_visual(daily_stats, league_id=league_id)
                weekly_processed = process_stats_for_visual(weekly_stats, league_id=league_id)
                os.makedirs(image_dir, exist_ok=True)
                if is_mlb:
                    daily_hitter, daily_pitcher = _split_mlb_stats(daily_processed)
                    weekly_hitter, weekly_pitcher = _split_mlb_stats(weekly_processed)
                    capture_html_to_png(render_stats_html(daily_hitter, weekly_hitter), h_path)
                    capture_html_to_png(render_stats_html(daily_pitcher, weekly_pitcher), p_path)
                    image_exists = os.path.exists(h_path) and os.path.exists(p_path)
                else:
                    combined_html = render_stats_html(daily_processed, weekly_processed)
                    capture_html_to_png(combined_html, img_path)
                    image_exists = os.path.exists(img_path)
                if image_exists:
                    return True, filenames
            except Exception as re_err:
                logging.error(f"[STATS] 從本地 JSON 渲染 {target_date} 戰績圖片失敗: {re_err}")

        if not allow_remote_fetch:
            return False, filenames

        # 2. 僅當 allow_remote_fetch=True 時，才啟動 WebAgentFetcher 現場生成
        logging.info(f"[STATS] 本地尚未有 {target_date} 圖片，正在啟動 WebAgentFetcher 現場生成...")
        try:
            from src.web_agent_fetcher import WebAgentFetcher
            from src.visualizer.processor import process_stats_for_visual
            from src.visualizer.renderer import render_stats_html
            from src.visualizer.capturer import capture_html_to_png
            from src.utils.path_utils import get_league_team_mapping_path

            mapping_file = get_league_team_mapping_path(league_id)
            team_mapping = {}
            if os.path.exists(mapping_file):
                try:
                    with open(mapping_file, "r", encoding="utf-8") as f:
                        team_mapping = json.load(f)
                except Exception:
                    pass

            fetcher = WebAgentFetcher(team_mapping=team_mapping, league_id=league_id)
            yahoo_date = tw_date_to_yahoo_date(target_date)
            daily_stats, weekly_stats = fetcher.fetch_daily_and_weekly_stats(league_id, yahoo_date)
            daily_processed = process_stats_for_visual(daily_stats, league_id=league_id)
            weekly_processed = process_stats_for_visual(weekly_stats, league_id=league_id)

            os.makedirs(image_dir, exist_ok=True)
            if is_mlb:
                daily_hitter, daily_pitcher = _split_mlb_stats(daily_processed)
                weekly_hitter, weekly_pitcher = _split_mlb_stats(weekly_processed)
                capture_html_to_png(render_stats_html(daily_hitter, weekly_hitter), h_path)
                capture_html_to_png(render_stats_html(daily_pitcher, weekly_pitcher), p_path)
                image_exists = os.path.exists(h_path) and os.path.exists(p_path)
            else:
                combined_html = render_stats_html(daily_processed, weekly_processed)
                capture_html_to_png(combined_html, img_path)
                image_exists = os.path.exists(img_path)
        except Exception as fe:
            from src.web_agent_fetcher import GamesInProgressError, NoGamesScheduledError
            if isinstance(fe, (GamesInProgressError, NoGamesScheduledError)):
                raise
            logging.error(f"[STATS] 現場生成戰績圖片失敗: {fe}")

        return image_exists, filenames

    def _reply_stats_images(
        self,
        event: MessageEvent,
        configuration: Configuration,
        sport: str,
        raw_id: str,
        target_date: str,
        filenames: list[str],
        notice_prefix: str | None = None
    ) -> None:
        from src.utils.bot_utils import get_public_server_url
        server_url = get_public_server_url()
        https_url = server_url.replace("http://", "https://")
        if not https_url.startswith("https://"):
            https_url = f"https://{https_url.lstrip('https://')}"

        if sport == "mlb":
            img_urls = [f"{https_url}/images/mlb/{raw_id}/{fname}" for fname in filenames]
        else:
            img_urls = [f"{https_url}/images/{sport}/{raw_id}/{filenames[0]}"]

        if notice_prefix:
            header_text = f"{notice_prefix}\n戰績數據日期：{target_date}"
        else:
            header_text = f"戰績數據日期：{target_date}"

        date_msg = TextMessage(text=header_text)
        messages = [date_msg] + [ImageMessage(original_content_url=url, preview_image_url=url) for url in img_urls]
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(reply_token=event.reply_token, messages=messages)
            )

    def _execute_historical_local_query(
        self,
        cmd_type: str,
        cmd_val: str | int | None,
        event: MessageEvent,
        configuration: Configuration,
        league_id: str,
        sport: str,
        raw_id: str,
        image_dir: str,
        now_tw: datetime,
        config: dict
    ) -> None:
        """
        處理歷史戰績查詢（#戰績昨天、#戰績上週、#戰績W<n>、#戰績<YYYYMMDD>）：
        只限當季且僅從本地現有數據取得；若非當季或找不到對應現有數據，則靜默不回應。
        """
        meta = load_league_metadata(league_id) or {}
        season_start_yahoo, season_end_yahoo, end_week, is_stale_meta = self._get_current_season_bounds(
            league_id=league_id,
            config=config,
            meta=meta,
            now_tw=now_tw,
        )

        target_date = None

        if cmd_type == "specific_date":
            target_date = str(cmd_val)
            if not self._is_tw_date_in_current_season(target_date, now_tw, season_start_yahoo, season_end_yahoo):
                logging.info(f"[STATS] 指定日期 {target_date} 非當季或為未來日期，靜默忽略。")
                return

        elif cmd_type == "yesterday":
            base_rule_date = get_stats_rule_date(now_tw)
            base_dt = datetime.strptime(base_rule_date, "%Y-%m-%d").date()
            target_date = (base_dt - timedelta(days=1)).strftime("%Y-%m-%d")
            if not self._is_tw_date_in_current_season(target_date, now_tw, season_start_yahoo, season_end_yahoo):
                logging.info(f"[STATS] 昨日日期 {target_date} 非當季範圍，靜默忽略。")
                return

        elif cmd_type in ("specific_week", "last_week"):
            entries = self._collect_current_season_entries(
                league_id=league_id,
                sport=sport,
                now_tw=now_tw,
                season_start_yahoo=season_start_yahoo,
                season_end_yahoo=season_end_yahoo,
                end_week=end_week,
                meta=meta,
                is_stale_meta=is_stale_meta,
            )
            if not entries:
                logging.info(f"[STATS] 本地尚無當季任何戰績數據，靜默忽略 {cmd_type}。")
                return

            if cmd_type == "specific_week":
                target_week = int(cmd_val)
            else:
                # 計算當前週數，上週 = current_week - 1
                base_rule_date = get_stats_rule_date(now_tw)
                base_yahoo_date = tw_date_to_yahoo_date(base_rule_date)
                current_week = self._resolve_week_for_yahoo_date(
                    yahoo_date_str=base_yahoo_date,
                    payload=None,
                    season_start_yahoo=season_start_yahoo,
                    end_week=end_week,
                    meta=meta,
                    is_stale_meta=is_stale_meta,
                )
                if current_week is None:
                    weeks_avail = [e["week"] for e in entries if e.get("week") is not None]
                    current_week = max(weeks_avail) if weeks_avail else 1
                target_week = current_week - 1

            if target_week < 1 or (end_week and target_week > end_week):
                logging.info(f"[STATS] 查詢週數 W{target_week} 超出當季範圍，靜默忽略。")
                return

            matching_dates = [e["tw_date"] for e in entries if e.get("week") == target_week]
            if not matching_dates:
                logging.info(f"[STATS] 本地找不到當季 W{target_week} 的戰績數據，靜默忽略。")
                return

            target_date = max(matching_dates)

        if not target_date:
            return

        image_exists, filenames = self._check_and_generate_images(
            league_id=league_id,
            sport=sport,
            image_dir=image_dir,
            target_date=target_date,
            allow_remote_fetch=False,
        )
        if not image_exists:
            logging.info(f"[STATS] 本地找不到 {target_date} 的戰績圖檔或 JSON 數據，靜默忽略。")
            return

        self._reply_stats_images(
            event=event,
            configuration=configuration,
            sport=sport,
            raw_id=raw_id,
            target_date=target_date,
            filenames=filenames,
            notice_prefix=None,
        )

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = event.message.text.strip()
        cmd_type, cmd_val = self.parse_command(user_text)
        if not cmd_type:
            return

        config = load_config()
        league_id = config.get("LEAGUE_ID")
        if not league_id:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="⚠️ 尚未設定或未綁定聯盟 ID，請先使用 #設置 進行綁定。")]
                    )
                )
            return

        now_tw = _get_now_tw()
        today_str = now_tw.strftime("%Y-%m-%d")
        yesterday_str = (now_tw.date() - timedelta(days=1)).strftime("%Y-%m-%d")
        current_hm = now_tw.strftime("%H:%M")
        sport, raw_id = parse_league_id(league_id)
        image_dir = get_league_image_dir(league_id)

        # 若為歷史查詢指令（昨天 / 上週 / W<n> / 指定日期），走純本地當季查詢流程
        if cmd_type != "combined":
            self._execute_historical_local_query(
                cmd_type=cmd_type,
                cmd_val=cmd_val,
                event=event,
                configuration=configuration,
                league_id=league_id,
                sport=sport,
                raw_id=raw_id,
                image_dir=image_dir,
                now_tw=now_tw,
                config=config,
            )
            return

        target_date, notice_prefix, is_today_query, state = self._resolve_target_date_and_notice(
            now_tw=now_tw,
            sport=sport,
            league_id=league_id,
        )
        base_update_hm = (state or {}).get("base_update_time") or "13:55"
        fallback_prev_date = resolve_latest_active_tw_date(
            sport,
            yesterday_str,
            league_id=league_id,
            prefer_existing_local=True,
        )

        # 若已達當日開放查詢時間 (is_today_query=True)，但本地尚無當日圖檔且當日比賽仍在進行，
        # 則順延 30 分鐘，改為提示用戶並回傳前一天（或最後一天比賽日）戰績
        is_mlb = (sport == "mlb")
        if is_today_query:
            if is_mlb:
                today_img_ready = (
                    os.path.exists(os.path.join(image_dir, f"{today_str}_combined_hitter.png"))
                    and os.path.exists(os.path.join(image_dir, f"{today_str}_combined_pitcher.png"))
                )
            else:
                today_img_ready = os.path.exists(os.path.join(image_dir, f"{today_str}_combined.png"))

            if not today_img_ready and are_games_still_in_progress(today_str, sport=sport):
                postponed = postpone_daily_schedule(
                    today_str,
                    current_hm=current_hm,
                    base_update_time=base_update_hm
                )
                query_open_time = postponed["query_open_time"]
                notice_prefix = f"因稍早或當前仍有比賽正在進行，請於{query_open_time}後再次查詢"
                target_date = fallback_prev_date
                is_today_query = False

        try:
            image_exists, filenames = self._check_and_generate_images(
                league_id=league_id,
                sport=sport,
                image_dir=image_dir,
                target_date=target_date,
                allow_remote_fetch=True,
            )
        except Exception as gip_err:
            from src.web_agent_fetcher import GamesInProgressError, NoGamesScheduledError
            if isinstance(gip_err, GamesInProgressError) and is_today_query:
                postponed = postpone_daily_schedule(
                    today_str,
                    current_hm=current_hm,
                    base_update_time=base_update_hm
                )
                query_open_time = postponed["query_open_time"]
                notice_prefix = f"因稍早或當前仍有比賽正在進行，請於{query_open_time}後再次查詢"
                target_date = fallback_prev_date
                is_today_query = False
                image_exists, filenames = self._check_and_generate_images(
                    league_id=league_id,
                    sport=sport,
                    image_dir=image_dir,
                    target_date=target_date,
                    allow_remote_fetch=True,
                )
            elif isinstance(gip_err, NoGamesScheduledError):
                target_date = fallback_prev_date
                is_today_query = False
                image_exists, filenames = self._check_and_generate_images(
                    league_id=league_id,
                    sport=sport,
                    image_dir=image_dir,
                    target_date=target_date,
                    allow_remote_fetch=True,
                )
            else:
                image_exists, filenames = False, []

        if image_exists:
            self._reply_stats_images(
                event=event,
                configuration=configuration,
                sport=sport,
                raw_id=raw_id,
                target_date=target_date,
                filenames=filenames,
                notice_prefix=notice_prefix,
            )
        else:
            if notice_prefix:
                fallback_text = f"{notice_prefix}\n戰績數據 ({target_date}) 正在更新中或尚未備妥，請稍後重試。"
            else:
                fallback_text = f"戰績數據 ({target_date}) 正在更新中或尚未備妥，請稍後重試。"
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=fallback_text)]
                    )
                )
