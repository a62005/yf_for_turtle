import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
import pytz

from src.utils.cache_utils import load_league_metadata
from src.utils.path_utils import (
    get_league_daily_dir,
    get_league_dir,
    get_league_image_dir,
    get_league_weekly_dir,
    parse_league_id,
)
from src.utils.time_utils import (
    get_fantasy_week,
    get_pacific_datetime,
    get_stats_rule_date,
    resolve_latest_active_tw_date,
    tw_date_to_yahoo_date,
)


def _get_now_tw() -> datetime:
    return datetime.now(pytz.timezone("Asia/Taipei"))


def _yahoo_date_to_tw_date(yahoo_date_str: str) -> str:
    dt = datetime.strptime(yahoo_date_str, "%Y-%m-%d")
    return (dt + timedelta(days=1)).strftime("%Y-%m-%d")


@dataclass(frozen=True)
class WeeklyFileEntry:
    yahoo_date: str
    week: int
    payload: dict


class LocalLeagueDataRepository:
    """
    本地聯賽資料倉儲：
    統一封裝本地 daily 與 weekly JSON 讀取（涵蓋當週即時週數據與歷史週結算數據）、
    當季開季與結束邊界判定、跨季過期 metadata 識別、無比賽日全 0 殘留檔過濾、
    日期所屬週次推算與當週對戰組合配對。
    """

    def get_current_season_bounds(
        self,
        league_id: str,
        config: dict,
        meta: dict | None,
        now_tw: datetime,
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
                season_start_yahoo = f"{now_tw.year}-10-01"
            return season_start_yahoo, None, None, True

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

    def is_tw_date_in_current_season(
        self,
        tw_date_str: str,
        now_tw: datetime,
        season_start_yahoo: str | None,
        season_end_yahoo: str | None,
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

    def resolve_week_for_yahoo_date(
        self,
        yahoo_date_str: str,
        payload: dict | None,
        season_start_yahoo: str | None,
        end_week: int | None,
        meta: dict | None,
        is_stale_meta: bool,
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

    def collect_current_season_entries(
        self,
        league_id: str,
        sport: str,
        now_tw: datetime,
        season_start_yahoo: str | None,
        season_end_yahoo: str | None,
        end_week: int | None,
        meta: dict | None,
        is_stale_meta: bool,
    ) -> list[dict]:
        """
        掃描本地現有的 image / daily / weekly 資料，回傳所有屬於「當季」的可用台灣日期清單（由舊到新排序）。
        每個元素為: {"tw_date": str, "yahoo_date": str, "week": int | None}
        """
        is_mlb = sport == "mlb"
        image_dir = get_league_image_dir(league_id)
        daily_dir = get_league_daily_dir(league_id)
        weekly_dir = get_league_weekly_dir(league_id)

        candidate_tw_dates: set[str] = set()
        payload_by_yahoo_date: dict[str, dict] = {}

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
            if not self.is_tw_date_in_current_season(tw_d, now_tw, season_start_yahoo, season_end_yahoo):
                continue
            y_d = tw_date_to_yahoo_date(tw_d)
            payload = payload_by_yahoo_date.get(y_d) or payload_by_yahoo_date.get(tw_d)
            w = self.resolve_week_for_yahoo_date(
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

    def load_local_weekly_data(
        self,
        league_id: str,
        preferred_tw_date: str | None = None,
        now_tw: datetime | None = None,
    ) -> dict | None:
        """
        讀取本地端 weekly 資料夾中的當週戰績數據：
        優先依據 #戰績 時間規則尋找對應美西日期的 date_<YYYY-MM-DD>_weekly.json，
        若該日檔案尚未產生，則自動退回讀取本地最新一天的 weekly JSON 檔案。
        """
        weekly_dir = get_league_weekly_dir(league_id)
        if not os.path.exists(weekly_dir):
            return None

        now_tw = now_tw or _get_now_tw()
        sport, _ = parse_league_id(league_id)
        base_tw_date = preferred_tw_date or get_stats_rule_date(now_tw)
        tw_rule_date = resolve_latest_active_tw_date(
            sport,
            base_tw_date,
            league_id=league_id,
            prefer_existing_local=True,
        )
        yahoo_date = tw_date_to_yahoo_date(tw_rule_date)

        candidate_names = [
            f"date_{yahoo_date}_weekly.json",
            f"date_{tw_rule_date}_weekly.json",
            f"{yahoo_date}_weekly.json",
            f"{tw_rule_date}_weekly.json",
        ]
        for fname in candidate_names:
            fpath = os.path.join(weekly_dir, fname)
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict) and data.get("team_stats"):
                        return data
                except Exception as e:
                    logging.warning(f"[LocalLeagueDataRepository] 讀取 {fpath} 失敗: {e}")

        dated_files = []
        week_files = []
        for fname in os.listdir(weekly_dir):
            if not fname.endswith(".json"):
                continue
            m = re.match(r"^date_(\d{4}-\d{2}-\d{2})_weekly\.json$", fname)
            if m:
                dated_files.append((m.group(1), os.path.join(weekly_dir, fname)))
                continue
            m_w = re.match(r"^week_(\d+)\.json$", fname)
            if m_w:
                week_files.append((int(m_w.group(1)), os.path.join(weekly_dir, fname)))

        dated_files.sort(key=lambda x: x[0], reverse=True)
        for _, fpath in dated_files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data.get("team_stats"):
                    return data
            except Exception:
                continue

        week_files.sort(key=lambda x: x[0], reverse=True)
        for w_num, fpath in week_files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data.get("team_stats"):
                    data.setdefault("week", w_num)
                    return data
            except Exception:
                continue

        return None

    def resolve_week_number(
        self,
        league_id: str,
        weekly_data: dict,
        config: dict,
        meta: dict | None = None,
    ) -> int:
        if isinstance(weekly_data, dict) and weekly_data.get("week") is not None:
            try:
                return int(weekly_data["week"])
            except (ValueError, TypeError):
                pass

        if meta is None:
            meta = load_league_metadata(league_id) or {}
        else:
            meta = meta or {}

        data_date = (weekly_data or {}).get("date")
        date_to_week = meta.get("date_to_week") or {}
        if data_date and data_date in date_to_week:
            try:
                return int(date_to_week[data_date])
            except (ValueError, TypeError):
                pass

        start_date = meta.get("start_date") or config.get("SEASON_START_DATE")
        end_date = meta.get("end_date")
        end_week = meta.get("end_week") or 24

        current_dt = get_pacific_datetime()
        if data_date:
            try:
                current_dt = pytz.timezone("US/Pacific").localize(datetime.strptime(data_date, "%Y-%m-%d"))
            except Exception:
                pass

        current_date_str = current_dt.strftime("%Y-%m-%d")

        next_season_raw = config.get("NEXT_SEASON_START_DATE") or meta.get("next_season_start_date")
        next_season_date = str(next_season_raw).strip()[:10] if next_season_raw else None
        if end_date and current_date_str > end_date:
            if next_season_date and next_season_date > end_date and current_date_str >= next_season_date:
                start_date = next_season_date
                end_date = None
                end_week = None
            else:
                try:
                    days_past_end = (
                        datetime.strptime(current_date_str, "%Y-%m-%d") - datetime.strptime(end_date, "%Y-%m-%d")
                    ).days
                except Exception:
                    days_past_end = 0
                if days_past_end > 90:
                    weekly_dir = get_league_weekly_dir(league_id)
                    season_dates = []
                    if os.path.exists(weekly_dir):
                        for fn in os.listdir(weekly_dir):
                            m = re.match(r"^date_(\d{4}-\d{2}-\d{2})_weekly\.json$", fn)
                            if m and m.group(1) > end_date:
                                season_dates.append(m.group(1))
                    if season_dates:
                        start_date = min(season_dates)
                        end_date = None
                        end_week = None
                    else:
                        return int(end_week)
                else:
                    return int(end_week)
        elif not start_date and next_season_date and current_date_str >= next_season_date:
            start_date = next_season_date

        if start_date:
            try:
                week = get_fantasy_week(start_date, current_dt)
                if end_week and week > int(end_week):
                    week = int(end_week)
                return max(1, week)
            except Exception:
                pass

        return 1

    def build_matchups_from_weekly_data(self, weekly_data: dict, team_mapping: dict) -> list[dict]:
        raw_teams = weekly_data.get("team_stats", []) or []
        enriched_teams = []
        team_by_id = {}

        for idx, t in enumerate(raw_teams, 1):
            tid = str(t.get("team_id") or idx)
            raw_name = t.get("name") or f"Team {tid}"
            official_name = t.get("official_name") or raw_name
            display_name = team_mapping.get(tid, raw_name)
            team_obj = {
                "team_id": tid,
                "name": display_name,
                "official_name": official_name,
                "stats": dict(t.get("stats") or {}),
            }
            enriched_teams.append(team_obj)
            team_by_id[tid] = team_obj

        matchups = []
        explicit_matchups = weekly_data.get("matchups")
        if isinstance(explicit_matchups, list) and explicit_matchups:
            for m in explicit_matchups:
                if not isinstance(m, dict):
                    continue
                if "team1" in m and "team2" in m and isinstance(m["team1"], dict) and isinstance(m["team2"], dict):
                    t1_raw, t2_raw = m["team1"], m["team2"]
                    t1_id = str(t1_raw.get("team_id", ""))
                    t2_id = str(t2_raw.get("team_id", ""))
                    t1 = team_by_id.get(t1_id) or {
                        "team_id": t1_id,
                        "name": team_mapping.get(t1_id, t1_raw.get("name", "Unknown")),
                        "official_name": t1_raw.get("official_name") or t1_raw.get("name", "Unknown"),
                        "stats": dict(t1_raw.get("stats") or {}),
                    }
                    t2 = team_by_id.get(t2_id) or {
                        "team_id": t2_id,
                        "name": team_mapping.get(t2_id, t2_raw.get("name", "Unknown")),
                        "official_name": t2_raw.get("official_name") or t2_raw.get("name", "Unknown"),
                        "stats": dict(t2_raw.get("stats") or {}),
                    }
                    matchups.append({"team1": t1, "team2": t2})
                else:
                    t1_id = str(m.get("team1_id", ""))
                    t2_id = str(m.get("team2_id", ""))
                    if t1_id in team_by_id and t2_id in team_by_id:
                        matchups.append({"team1": team_by_id[t1_id], "team2": team_by_id[t2_id]})

        if matchups:
            return matchups

        for i in range(0, len(enriched_teams) - 1, 2):
            matchups.append({
                "team1": enriched_teams[i],
                "team2": enriched_teams[i + 1],
            })
        return matchups

    def load_weekly_data_for_query(
        self,
        league_id: str,
        config: dict,
        now_tw: datetime,
        week_mode: str | None,
        week_num: int | None,
        meta: dict | None = None,
    ) -> tuple[dict | None, int | None, bool]:
        """
        根據查詢模式載入對應週次的 weekly JSON 數據。
        回傳: (weekly_data, resolved_week, is_historical_silent_miss)
        """
        preferred_tw_date = get_stats_rule_date(now_tw)

        if week_mode is None:
            weekly_data = self.load_local_weekly_data(
                league_id,
                preferred_tw_date=preferred_tw_date,
                now_tw=now_tw,
            )
            if not weekly_data:
                return None, None, False
            week = self.resolve_week_number(league_id, weekly_data, config, meta=meta)
            return weekly_data, week, False

        if meta is None:
            meta = load_league_metadata(league_id) or {}
        else:
            meta = meta or {}

        season_start_yahoo, season_end_yahoo, end_week, is_stale_meta = self.get_current_season_bounds(
            league_id=league_id,
            config=config,
            meta=meta,
            now_tw=now_tw,
        )

        weekly_dir = get_league_weekly_dir(league_id)
        if not os.path.exists(weekly_dir):
            return None, None, True

        weekly_entries: list[WeeklyFileEntry] = []
        for fn in sorted(os.listdir(weekly_dir)):
            if not fn.endswith(".json"):
                continue
            m = re.match(r"^(?:date_)?(\d{4}-\d{2}-\d{2})_weekly\.json$", fn)
            if not m:
                continue
            y_date = m.group(1)
            fpath = os.path.join(weekly_dir, fn)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict) or not data.get("team_stats"):
                    continue
            except Exception:
                continue

            if season_start_yahoo and y_date < season_start_yahoo:
                continue
            if season_end_yahoo and y_date > season_end_yahoo:
                continue

            w = self.resolve_week_for_yahoo_date(
                yahoo_date_str=y_date,
                payload=data,
                season_start_yahoo=season_start_yahoo,
                end_week=end_week,
                meta=meta,
                is_stale_meta=is_stale_meta,
            )
            if w is not None:
                weekly_entries.append(WeeklyFileEntry(yahoo_date=y_date, week=int(w), payload=data))

        if not weekly_entries:
            return None, None, True

        base_yahoo_date = tw_date_to_yahoo_date(preferred_tw_date)
        current_week = self.resolve_week_for_yahoo_date(
            yahoo_date_str=base_yahoo_date,
            payload=None,
            season_start_yahoo=season_start_yahoo,
            end_week=end_week,
            meta=meta,
            is_stale_meta=is_stale_meta,
        )
        if current_week is None:
            current_week = max(e.week for e in weekly_entries)

        target_week = (current_week - 1) if week_mode == "last_week" else int(week_num)
        if target_week < 1 or (end_week and target_week > end_week):
            return None, None, True

        if target_week == current_week:
            live_data = self.load_local_weekly_data(
                league_id,
                preferred_tw_date=preferred_tw_date,
                now_tw=now_tw,
            )
            if live_data:
                live_w = self.resolve_week_number(league_id, live_data, config, meta=meta)
                if live_w == target_week:
                    return live_data, target_week, False

        matching = [e for e in weekly_entries if e.week == target_week]
        if not matching:
            return None, None, True

        matching.sort(key=lambda x: x.yahoo_date, reverse=True)
        return matching[0].payload, target_week, False

    @staticmethod
    def is_daily_payload_all_zero(data: dict) -> bool:
        """檢查一份 daily JSON 數據是否全聯盟當日出賽人數與計數數據皆為 0（無比賽日殘留檔）。"""
        if not isinstance(data, dict):
            return True
        teams = data.get("team_stats")
        if not isinstance(teams, list) or not teams:
            return True
        counting_keys = (
            "PTS", "REB", "AST", "ST", "STL", "BLK", "TO", "3PTM", "3PT", "3PM", "DD", "TD",
            "R", "H", "HR", "RBI", "SB", "BB", "W", "K", "QS",
        )
        for t in teams:
            st = (t.get("stats") or {}) if isinstance(t, dict) else {}
            try:
                if int(st.get("Today Player") or 0) > 0:
                    return False
            except (ValueError, TypeError):
                pass
            for ck in counting_keys:
                if ck in st:
                    try:
                        if float(st.get(ck) or 0) > 0:
                            return False
                    except (ValueError, TypeError):
                        pass
        return True

    def load_default_local_daily_data(
        self,
        league_id: str,
        now_tw: datetime | None = None,
    ) -> tuple[dict | None, str | None]:
        """
        讀取預設當日的本地 daily 數據（依據 #戰績 14:00 切日規則與無比賽日回退至最後一天比賽數據，若無則退回最新一天非全 0 檔案）。
        回傳 (daily_data, display_tw_date_str)，顯示日期與 #戰績 完全同步。
        """
        daily_dir = get_league_daily_dir(league_id)
        if not os.path.exists(daily_dir):
            return None, None

        sport, _ = parse_league_id(league_id)
        now_tw = now_tw or _get_now_tw()
        tw_rule_date = resolve_latest_active_tw_date(
            sport,
            get_stats_rule_date(now_tw),
            league_id=league_id,
            prefer_existing_local=True,
        )
        yahoo_date = tw_date_to_yahoo_date(tw_rule_date)

        candidates = [
            (tw_rule_date, f"date_{yahoo_date}.json"),
            (tw_rule_date, f"{yahoo_date}.json"),
            (tw_rule_date, f"date_{tw_rule_date}.json"),
            (tw_rule_date, f"{tw_rule_date}.json"),
        ]
        for display_label, fname in candidates:
            fpath = os.path.join(daily_dir, fname)
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict) and data.get("team_stats") and not self.is_daily_payload_all_zero(data):
                        return data, display_label
                except Exception as e:
                    logging.warning(f"[LocalLeagueDataRepository] 讀取 {fpath} 失敗: {e}")

        dated_files = []
        for fname in os.listdir(daily_dir):
            if not fname.endswith(".json"):
                continue
            m = re.match(r"^(?:date_)?(\d{4}-\d{2}-\d{2})\.json$", fname)
            if m:
                dated_files.append((m.group(1), os.path.join(daily_dir, fname)))

        dated_files.sort(key=lambda x: x[0], reverse=True)
        for d_str, fpath in dated_files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data.get("team_stats") and not self.is_daily_payload_all_zero(data):
                    raw_d = data.get("date") or d_str
                    try:
                        tw_d = (datetime.strptime(raw_d, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                    except Exception:
                        tw_d = raw_d
                    return data, tw_d
            except Exception:
                continue

        return None, None

    def resolve_week_for_date(
        self,
        league_id: str,
        date_str: str,
        daily_data: dict,
        config: dict,
        meta: dict | None = None,
    ) -> int:
        if isinstance(daily_data, dict) and daily_data.get("week") is not None:
            try:
                return int(daily_data["week"])
            except (ValueError, TypeError):
                pass

        if meta is None:
            meta = load_league_metadata(league_id) or {}
        else:
            meta = meta or {}

        date_to_week = meta.get("date_to_week") or {}
        if date_str and date_str in date_to_week:
            try:
                return int(date_to_week[date_str])
            except (ValueError, TypeError):
                pass

        start_date = meta.get("start_date") or config.get("SEASON_START_DATE")
        end_date = meta.get("end_date")
        end_week = meta.get("end_week")

        next_season_raw = config.get("NEXT_SEASON_START_DATE") or meta.get("next_season_start_date")
        next_season_date = str(next_season_raw).strip()[:10] if next_season_raw else None
        if date_str and end_date and date_str > end_date:
            if next_season_date and next_season_date > end_date and date_str >= next_season_date:
                start_date = next_season_date
                end_week = None
            else:
                try:
                    days_past_end = (
                        datetime.strptime(date_str, "%Y-%m-%d") - datetime.strptime(end_date, "%Y-%m-%d")
                    ).days
                except Exception:
                    days_past_end = 0
                if days_past_end > 90:
                    daily_dir = get_league_daily_dir(league_id)
                    season_dates = []
                    if os.path.exists(daily_dir):
                        for fn in os.listdir(daily_dir):
                            m = re.match(r"^(?:date_)?(\d{4}-\d{2}-\d{2})\.json$", fn)
                            if m and m.group(1) > end_date:
                                season_dates.append(m.group(1))
                    if season_dates:
                        start_date = min(season_dates)
                        end_week = None
        elif not start_date and next_season_date and date_str and date_str >= next_season_date:
            start_date = next_season_date

        target_week = 1
        if start_date and date_str:
            try:
                target_dt = pytz.timezone("US/Pacific").localize(datetime.strptime(date_str, "%Y-%m-%d"))
                target_week = get_fantasy_week(start_date, target_dt)
            except Exception:
                try:
                    target_week = get_fantasy_week(start_date)
                except Exception:
                    target_week = 1

        if end_week and target_week > int(end_week):
            target_week = int(end_week)
        return max(1, int(target_week))

    def load_matching_weekly_data(
        self,
        league_id: str,
        daily_date: str,
        target_week: int,
        config: dict,
        meta: dict | None = None,
    ) -> dict | None:
        weekly_dir = get_league_weekly_dir(league_id)
        if not os.path.exists(weekly_dir):
            return None

        direct_candidates = []
        if daily_date:
            yahoo_equiv = tw_date_to_yahoo_date(daily_date)
            direct_candidates.extend([
                f"date_{daily_date}_weekly.json",
                f"{daily_date}_weekly.json",
                f"date_{yahoo_equiv}_weekly.json",
                f"{yahoo_equiv}_weekly.json",
            ])
        if target_week:
            direct_candidates.append(f"week_{target_week}.json")

        for fname in direct_candidates:
            fpath = os.path.join(weekly_dir, fname)
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict) and data.get("team_stats"):
                        return data
                except Exception:
                    continue

        dated_files = []
        for fname in os.listdir(weekly_dir):
            if not fname.endswith(".json"):
                continue
            m = re.match(r"^date_(\d{4}-\d{2}-\d{2})_weekly\.json$", fname)
            if m:
                dated_files.append((m.group(1), os.path.join(weekly_dir, fname)))

        dated_files.sort(key=lambda x: x[0], reverse=True)
        latest_valid = None
        for d_str, fpath in dated_files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict) or not data.get("team_stats"):
                    continue
                if latest_valid is None:
                    latest_valid = data
                file_week = self.resolve_week_for_date(league_id, d_str, data, config, meta=meta)
                if target_week and file_week == target_week:
                    return data
            except Exception:
                continue

        return latest_valid

    @staticmethod
    def find_team_entry(data: dict | None, team_id: str | None, nickname: str, mapping: dict) -> dict | None:
        if not isinstance(data, dict):
            return None
        teams = data.get("team_stats") or []
        if team_id:
            for t in teams:
                if str(t.get("team_id", "")) == str(team_id):
                    return t
        for t in teams:
            t_id = str(t.get("team_id", ""))
            mapped_name = mapping.get(t_id)
            if nickname in (mapped_name, t.get("name"), t.get("official_name")):
                return t
        return None

    def is_team_nickname_in_weekly_data(
        self,
        league_id: str,
        nickname: str,
        now_tw: datetime | None = None,
    ) -> bool:
        """
        檢查指定 nickname 是否存在於本地 weekly 資料夾（當週或任一歷史週 JSON）的 team_stats 中。
        """
        if not league_id or not nickname:
            return False
        n_lower = nickname.lower()

        weekly_data = self.load_local_weekly_data(league_id, now_tw=now_tw)
        if weekly_data:
            for t in weekly_data.get("team_stats", []):
                if (
                    str(t.get("name") or "").lower() == n_lower
                    or str(t.get("official_name") or "").lower() == n_lower
                ):
                    return True

        weekly_dir = get_league_weekly_dir(league_id)
        if os.path.exists(weekly_dir):
            for fn in sorted(os.listdir(weekly_dir), reverse=True):
                if not fn.endswith(".json"):
                    continue
                fpath = os.path.join(weekly_dir, fn)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    for t in (data or {}).get("team_stats", []):
                        if (
                            str(t.get("name") or "").lower() == n_lower
                            or str(t.get("official_name") or "").lower() == n_lower
                        ):
                            return True
                except Exception:
                    continue
        return False

    def load_local_stats_pair(
        self,
        league_id: str,
        tw_date_str: str,
        season_start_yahoo: str | None = None,
        end_week: int | None = None,
        meta: dict | None = None,
        is_stale_meta: bool = False,
    ) -> tuple[dict | None, dict | None]:
        """
        從本地端 daily/ 與 weekly/ 讀取指定台灣日期對應的 JSON 數據（絕不呼叫網路爬蟲）。
        """
        daily_dir = get_league_daily_dir(league_id)
        weekly_dir = get_league_weekly_dir(league_id)
        yahoo_date = tw_date_to_yahoo_date(tw_date_str)

        daily_stats = None
        if os.path.exists(daily_dir):
            for fname in (
                f"date_{yahoo_date}.json",
                f"{yahoo_date}.json",
                f"date_{tw_date_str}.json",
                f"{tw_date_str}.json",
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
                f"date_{tw_date_str}_weekly.json",
                f"{tw_date_str}_weekly.json",
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

            if weekly_stats is None:
                resolved_w = None
                if isinstance(daily_stats, dict) and daily_stats.get("week"):
                    resolved_w = daily_stats["week"]
                elif season_start_yahoo or meta:
                    resolved_w = self.resolve_week_for_yahoo_date(
                        yahoo_date_str=yahoo_date,
                        payload=daily_stats,
                        season_start_yahoo=season_start_yahoo,
                        end_week=end_week,
                        meta=meta,
                        is_stale_meta=is_stale_meta,
                    )
                if resolved_w:
                    w_fpath = os.path.join(weekly_dir, f"week_{resolved_w}.json")
                    if os.path.exists(w_fpath):
                        try:
                            with open(w_fpath, "r", encoding="utf-8") as f:
                                data = json.load(f)
                            if isinstance(data, dict) and data.get("team_stats"):
                                weekly_stats = data
                        except Exception:
                            pass

        return daily_stats, weekly_stats
