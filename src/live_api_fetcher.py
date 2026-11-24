import logging
import re
from datetime import datetime, timedelta
from typing import Any
import pytz
import requests


class EspnLivePlayerFetcher:
    """
    獨立的 ESPN 即時 NBA 球員數據擷取器（遵循 ADR-0001，與舊有 YahooFantasyFetcher 完全隔離）。
    串接免金鑰的 ESPN Search API、Scoreboard API 與 Game Summary Boxscore API。
    """

    SEARCH_URL = "https://site.web.api.espn.com/apis/common/v3/search"
    SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
    SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"
    GAMELOG_URL_TEMPLATE = (
        "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{athlete_id}/gamelog"
    )

    def __init__(self, timeout: int = 10) -> None:
        self.timeout = timeout

    @staticmethod
    def _extract_id_from_uid(uid: str) -> str:
        if not uid:
            return ""
        m = re.search(r"a:(\d+)", str(uid))
        if m:
            return m.group(1)
        return ""

    @staticmethod
    def _is_nba_player_item(item: dict) -> bool:
        if not isinstance(item, dict):
            return False
        item_type = str(item.get("type", "")).lower()
        if item_type and item_type not in ("player", "athlete"):
            return False

        league = item.get("league")
        if isinstance(league, dict):
            league_str = str(league.get("abbreviation") or league.get("slug") or "").lower()
        else:
            league_str = str(league or "").lower()

        default_league = str(item.get("defaultLeagueSlug") or "").lower()
        sport = str(item.get("sport") or "").lower()

        if "nba" in league_str or "nba" in default_league:
            return True
        if sport == "basketball" and (not league_str or "nba" in league_str):
            return True
        return False

    def _normalize_player_search_item(self, item: dict) -> dict | None:
        athlete_id = str(item.get("id") or self._extract_id_from_uid(item.get("uid", ""))).strip()
        english_name = str(item.get("displayName") or item.get("name") or "").strip()
        if not athlete_id or not english_name:
            return None

        team_id = ""
        team_abbr = ""
        team_name = ""

        team_rels = item.get("teamRelationships")
        if isinstance(team_rels, list) and team_rels:
            core = team_rels[0].get("core") if isinstance(team_rels[0], dict) else None
            if isinstance(core, dict):
                team_id = str(core.get("id") or "").strip()
                team_abbr = str(core.get("abbreviation") or "").strip().upper()
                team_name = str(core.get("displayName") or core.get("name") or "").strip()

        team_obj = item.get("team")
        if isinstance(team_obj, dict):
            team_id = team_id or str(team_obj.get("id") or "").strip()
            team_abbr = team_abbr or str(team_obj.get("abbreviation") or "").strip().upper()
            team_name = team_name or str(team_obj.get("displayName") or team_obj.get("name") or "").strip()

        if not team_name and item.get("subtitle"):
            team_name = str(item.get("subtitle")).strip()

        jersey_raw = item.get("jersey") if item.get("jersey") is not None else item.get("jerseyNumber")
        jersey_number = str(jersey_raw).strip().lstrip("#") if jersey_raw is not None else ""

        pos_raw = item.get("position")
        if isinstance(pos_raw, dict):
            position = str(pos_raw.get("abbreviation") or pos_raw.get("displayName") or "").strip()
        elif pos_raw is not None:
            position = str(pos_raw).strip()
        else:
            position = ""

        return {
            "athlete_id": athlete_id,
            "english_name": english_name,
            "team_id": team_id,
            "team_abbr": team_abbr,
            "team_name": team_name,
            "jersey_number": jersey_number,
            "position": position,
        }

    def search_player(self, query_name: str) -> dict | None:
        """
        透過 ESPN Search API 檢索 NBA 現役球員，回傳標準化結構：
        {
            "athlete_id": str,
            "english_name": str,
            "team_id": str,
            "team_abbr": str,
            "team_name": str,
            "jersey_number": str,
            "position": str,
        }
        """
        if not query_name or not str(query_name).strip():
            return None

        params = {
            "query": str(query_name).strip(),
            "limit": 10,
            "type": "player",
        }
        try:
            resp = requests.get(self.SEARCH_URL, params=params, timeout=self.timeout)
            if resp.status_code != 200:
                logging.warning(f"[EspnLivePlayerFetcher] Search API status {resp.status_code} for {query_name}")
                return None
            data = resp.json()
        except Exception as e:
            logging.error(f"[EspnLivePlayerFetcher] Search API error for {query_name}: {e}")
            return None

        candidates: list[dict] = []
        if isinstance(data.get("items"), list):
            candidates.extend(data["items"])
        if isinstance(data.get("results"), list):
            for group in data["results"]:
                if isinstance(group, dict) and str(group.get("type", "")).lower() in ("player", "athlete", ""):
                    contents = group.get("contents")
                    if isinstance(contents, list):
                        candidates.extend(contents)

        for item in candidates:
            if not self._is_nba_player_item(item):
                continue
            normalized = self._normalize_player_search_item(item)
            if normalized:
                return normalized

        return None

    @staticmethod
    def _parse_made_attempted(raw_val: Any) -> tuple[int, int]:
        if raw_val is None:
            return 0, 0
        s = str(raw_val).strip()
        if not s or s == "-":
            return 0, 0
        for sep in ("-", "/"):
            if sep in s:
                parts = s.split(sep, 1)
                try:
                    return int(float(parts[0].strip())), int(float(parts[1].strip()))
                except (ValueError, TypeError):
                    return 0, 0
        try:
            val = int(float(s))
            return val, 0
        except (ValueError, TypeError):
            return 0, 0

    @staticmethod
    def _parse_int(raw_val: Any) -> int:
        if raw_val is None:
            return 0
        s = str(raw_val).strip()
        if not s or s == "-":
            return 0
        try:
            return int(round(float(s)))
        except (ValueError, TypeError):
            return 0

    def compute_fantasy_stats_from_raw(self, raw_stats: dict) -> dict:
        """
        將 ESPN Boxscore 原始投籃字串（如 "12-19"）與各項計數轉換為與 #戰績 完全相容的統計字典，
        包含 MIN、FGM/A、FG%、FTM/A、FT%、3PT、PTS、REB、AST、ST、BLK、TO，
        並自動計算雙十 DD、大三元 TD 與助攻失誤比 A/T。
        """
        if not isinstance(raw_stats, dict):
            raw_stats = {}

        fg_raw = (
            raw_stats.get("FG")
            if "FG" in raw_stats
            else (raw_stats.get("FGM/A") if "FGM/A" in raw_stats else raw_stats.get("FGM/FGA"))
        )
        fgm, fga = self._parse_made_attempted(fg_raw)
        fgm_a_str = f"{fgm}/{fga}"
        fg_pct_str = f"{(fgm / fga) * 100:.1f}%" if fga > 0 else "-"

        ft_raw = (
            raw_stats.get("FT")
            if "FT" in raw_stats
            else (raw_stats.get("FTM/A") if "FTM/A" in raw_stats else raw_stats.get("FTM/FTA"))
        )
        ftm, fta = self._parse_made_attempted(ft_raw)
        ftm_a_str = f"{ftm}/{fta}"
        ft_pct_str = f"{(ftm / fta) * 100:.1f}%" if fta > 0 else "-"

        t3_raw = (
            raw_stats.get("3PT")
            if "3PT" in raw_stats
            else (raw_stats.get("3PTM") if "3PTM" in raw_stats else raw_stats.get("3PM"))
        )
        t3_str = str(t3_raw or "").strip()
        if "-" in t3_str or "/" in t3_str:
            tpm, tpa = self._parse_made_attempted(t3_str)
            t3_pct_str = f"{(tpm / tpa) * 100:.1f}%" if tpa > 0 else "-"
        else:
            tpm = self._parse_int(t3_raw)
            tpa = 0
            t3_pct_str = "-"

        pts = self._parse_int(raw_stats.get("PTS"))
        reb = self._parse_int(raw_stats.get("REB"))
        oreb = self._parse_int(raw_stats.get("OREB"))
        dreb = self._parse_int(raw_stats.get("DREB"))
        ast = self._parse_int(raw_stats.get("AST"))
        stl = self._parse_int(raw_stats.get("STL") if "STL" in raw_stats else raw_stats.get("ST"))
        blk = self._parse_int(raw_stats.get("BLK"))
        to = self._parse_int(raw_stats.get("TO"))

        double_digit_cats = sum(1 for v in (pts, reb, ast, stl, blk) if v >= 10)
        dd = 1 if double_digit_cats >= 2 else 0
        td = 1 if double_digit_cats >= 3 else 0

        if to > 0:
            at_ratio = f"{ast / to:.2f}"
        elif ast > 0:
            at_ratio = f"{float(ast):.2f}"
        else:
            at_ratio = "0.00"

        minutes_raw = raw_stats.get("MIN")
        minutes_str = str(minutes_raw).strip() if minutes_raw not in (None, "") else "0"

        return {
            "MIN": minutes_str,
            "FGM/A": fgm_a_str,
            "FGM/FGA": fgm_a_str,
            "FG%": fg_pct_str,
            "FTM/A": ftm_a_str,
            "FTM/FTA": ftm_a_str,
            "FT%": ft_pct_str,
            "3PT": str(tpm),
            "3PTM": str(tpm),
            "3PM": str(tpm),
            "3PT%": t3_pct_str,
            "PTS": str(pts),
            "REB": str(reb),
            "OREB": str(oreb),
            "DREB": str(dreb),
            "AST": str(ast),
            "ST": str(stl),
            "STL": str(stl),
            "BLK": str(blk),
            "TO": str(to),
            "DD": str(dd),
            "TD": str(td),
            "A/T": at_ratio,
            "AST/TO": at_ratio,
        }

    def _fetch_scoreboard(self, date_yyyymmdd: str) -> dict:
        url = f"{self.SCOREBOARD_URL}?dates={date_yyyymmdd}"
        try:
            resp = requests.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json() or {}
        except Exception as e:
            logging.error(f"[EspnLivePlayerFetcher] Scoreboard API error for {date_yyyymmdd}: {e}")
        return {}

    def _fetch_summary(self, event_id: str) -> dict:
        url = f"{self.SUMMARY_URL}?event={event_id}"
        try:
            resp = requests.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json() or {}
        except Exception as e:
            logging.error(f"[EspnLivePlayerFetcher] Summary API error for event {event_id}: {e}")
        return {}

    def _fetch_gamelog(self, athlete_id: str) -> dict:
        if not athlete_id:
            return {}
        url = self.GAMELOG_URL_TEMPLATE.format(athlete_id=athlete_id)
        try:
            resp = requests.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json() or {}
        except Exception as e:
            logging.error(f"[EspnLivePlayerFetcher] Gamelog API error for athlete {athlete_id}: {e}")
        return {}

    @staticmethod
    def _extract_yyyy_mm_dd(raw_date: Any) -> str:
        if not raw_date:
            return ""
        s = str(raw_date).strip()
        m = re.match(r"^(\d{4}-\d{2}-\d{2})", s)
        if m:
            return m.group(1)
        m2 = re.match(r"^(\d{4})(\d{2})(\d{2})", s)
        if m2:
            return f"{m2.group(1)}-{m2.group(2)}-{m2.group(3)}"
        return ""

    @staticmethod
    def _build_gamelog_score_text(event_meta: dict, player_info: dict) -> str:
        if not isinstance(event_meta, dict):
            return ""
        if event_meta.get("score_text"):
            return str(event_meta["score_text"]).strip()
        if event_meta.get("competitions"):
            return EspnLivePlayerFetcher._build_score_text(event_meta["competitions"][0])

        team_obj = event_meta.get("team") if isinstance(event_meta.get("team"), dict) else {}
        opp_obj = event_meta.get("opponent") if isinstance(event_meta.get("opponent"), dict) else {}
        team_abbr = (
            str(team_obj.get("abbreviation") or player_info.get("team_abbr") or "TEAM")
            .strip()
            .upper()
        )
        opp_abbr = str(opp_obj.get("abbreviation") or "OPP").strip().upper()

        score_raw = str(event_meta.get("score") or "").strip()
        m = re.search(r"(\d+)\s*[-:]\s*(\d+)", score_raw)
        if m:
            s_a, s_b = int(m.group(1)), int(m.group(2))
            result = str(event_meta.get("gameResult") or "").strip().upper()
            if result == "W":
                team_score, opp_score = max(s_a, s_b), min(s_a, s_b)
            elif result == "L":
                team_score, opp_score = min(s_a, s_b), max(s_a, s_b)
            else:
                team_score, opp_score = s_a, s_b
            return f"{team_abbr} {team_score} : {opp_score} {opp_abbr}"

        home_score = event_meta.get("homeTeamScore")
        away_score = event_meta.get("awayTeamScore")
        if home_score is not None and away_score is not None:
            at_vs = str(event_meta.get("atVs") or "").strip().lower()
            if at_vs == "@":
                return f"{team_abbr} {away_score} : {home_score} {opp_abbr}"
            return f"{team_abbr} {home_score} : {away_score} {opp_abbr}"

        return ""

    def _extract_latest_game_from_gamelog(
        self,
        gamelog_data: dict,
        player_info: dict,
        max_date_str: str = "",
        exclude_event_id: str = "",
        notice_banner: str | None = None,
    ) -> dict | None:
        if not isinstance(gamelog_data, dict) or not gamelog_data:
            return None

        default_labels = (
            gamelog_data.get("labels")
            or gamelog_data.get("names")
            or [
                "MIN", "FG", "FG%", "3PT", "3P%", "FT", "FT%",
                "REB", "AST", "BLK", "STL", "PF", "TO", "PTS",
            ]
        )

        events_meta_map: dict[str, dict] = {}
        raw_events = gamelog_data.get("events")
        if isinstance(raw_events, dict):
            for k, v in raw_events.items():
                if isinstance(v, dict):
                    events_meta_map[str(k)] = v
        elif isinstance(raw_events, list):
            for item in raw_events:
                if isinstance(item, dict):
                    eid = str(item.get("id") or item.get("eventId") or "")
                    if eid:
                        events_meta_map[eid] = item

        stat_entries: list[tuple[str, list[str], list[Any], dict]] = []
        season_types = gamelog_data.get("seasonTypes")
        if isinstance(season_types, list):
            for st in season_types:
                if not isinstance(st, dict):
                    continue
                st_labels = st.get("labels") or st.get("names") or default_labels
                for cat in st.get("categories") or []:
                    if not isinstance(cat, dict):
                        continue
                    cat_labels = cat.get("labels") or cat.get("names") or st_labels
                    for ev in cat.get("events") or []:
                        if not isinstance(ev, dict):
                            continue
                        eid = str(ev.get("eventId") or ev.get("id") or "").strip()
                        stats_list = ev.get("stats") or []
                        if not stats_list:
                            continue
                        meta = events_meta_map.get(eid, ev)
                        stat_entries.append((eid, cat_labels, stats_list, meta))

        if not stat_entries and isinstance(raw_events, list):
            for ev in raw_events:
                if not isinstance(ev, dict):
                    continue
                eid = str(ev.get("eventId") or ev.get("id") or "").strip()
                stats_list = ev.get("stats") or []
                if not stats_list:
                    continue
                ev_labels = ev.get("labels") or ev.get("names") or default_labels
                stat_entries.append((eid, ev_labels, stats_list, ev))

        candidates: list[tuple[str, str, list[str], list[Any], dict]] = []
        for eid, labels, stats_list, meta in stat_entries:
            if exclude_event_id and eid == exclude_event_id:
                continue
            g_date = self._extract_yyyy_mm_dd(meta.get("gameDate") or meta.get("date"))
            if max_date_str and g_date and g_date > max_date_str:
                continue
            candidates.append((g_date, eid, labels, stats_list, meta))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[0], reverse=True)
        best_date, best_eid, best_labels, best_stats, best_meta = candidates[0]

        raw_map = dict(zip(best_labels, best_stats))
        computed = self.compute_fantasy_stats_from_raw(raw_map)
        score_text = self._build_gamelog_score_text(best_meta, player_info)

        return {
            "event_id": best_eid,
            "game_date": best_date,
            "game_state": "post",
            "status_label": "🏁 FINAL",
            "score_text": score_text,
            "minutes": computed.get("MIN", "0"),
            "stats": computed,
            "notice_banner": notice_banner,
        }

    @staticmethod
    def _match_team_in_event(event: dict, team_id: str, team_abbr: str) -> dict | None:
        competitions = event.get("competitions") or []
        if not competitions:
            return None
        comp = competitions[0]
        for competitor in comp.get("competitors") or []:
            team = competitor.get("team") or {}
            c_id = str(team.get("id") or "").strip()
            c_abbr = str(team.get("abbreviation") or "").strip().upper()
            if (team_id and c_id == str(team_id).strip()) or (
                team_abbr and c_abbr == str(team_abbr).strip().upper()
            ):
                return comp
        return None

    @staticmethod
    def _build_score_text(competition: dict) -> str:
        competitors = competition.get("competitors") or []
        if len(competitors) < 2:
            return ""
        c0, c1 = competitors[0], competitors[1]
        t0 = (c0.get("team") or {}).get("abbreviation") or "TEAM1"
        t1 = (c1.get("team") or {}).get("abbreviation") or "TEAM2"
        s0 = c0.get("score") if c0.get("score") is not None else "0"
        s1 = c1.get("score") if c1.get("score") is not None else "0"
        return f"{t0} {s0} : {s1} {t1}"

    @staticmethod
    def _build_status_label(competition: dict, event: dict) -> tuple[str, str]:
        status = competition.get("status") or event.get("status") or {}
        status_type = status.get("type") or {}
        state = str(status_type.get("state") or "").lower()
        short_detail = str(status_type.get("shortDetail") or status_type.get("detail") or "").strip()
        period = status.get("period")
        display_clock = str(status.get("displayClock") or "").strip()

        if state == "in":
            if "halftime" in short_detail.lower():
                return state, "🔴 LIVE • Halftime"
            if short_detail.upper().startswith("Q") or short_detail.upper().startswith("OT"):
                return state, f"🔴 LIVE • {short_detail}"
            if period and display_clock:
                try:
                    p_int = int(period)
                    q_label = f"Q{p_int}" if p_int <= 4 else f"OT{p_int - 4}"
                except (ValueError, TypeError):
                    q_label = f"Q{period}"
                return state, f"🔴 LIVE • {q_label} {display_clock}"
            if short_detail:
                return state, f"🔴 LIVE • {short_detail}"
            return state, "🔴 LIVE"

        if state == "post":
            return state, "🏁 FINAL"

        return state, short_detail or "Scheduled"

    def _extract_player_from_boxscore(self, summary_data: dict, player_info: dict) -> dict | None:
        target_id = str(player_info.get("athlete_id") or "").strip()
        target_name = str(player_info.get("english_name") or "").strip().lower()

        boxscore = summary_data.get("boxscore") or {}
        for team_group in boxscore.get("players") or []:
            for stat_block in team_group.get("statistics") or []:
                labels = stat_block.get("labels") or stat_block.get("names") or [
                    "MIN", "FG", "3PT", "FT", "OREB", "DREB",
                    "REB", "AST", "STL", "BLK", "TO", "PF", "+/-", "PTS",
                ]
                for ath_entry in stat_block.get("athletes") or []:
                    ath = ath_entry.get("athlete") or {}
                    a_id = str(ath.get("id") or "").strip()
                    a_name = str(ath.get("displayName") or "").strip().lower()
                    if (target_id and a_id == target_id) or (target_name and a_name == target_name):
                        if not player_info.get("jersey_number") and ath.get("jersey"):
                            player_info["jersey_number"] = str(ath["jersey"]).strip().lstrip("#")
                        if not player_info.get("position") and isinstance(ath.get("position"), dict):
                            player_info["position"] = str(ath["position"].get("abbreviation") or "").strip()
                        return {
                            "did_not_play": bool(ath_entry.get("didNotPlay")),
                            "reason": str(ath_entry.get("reason") or "DNP").strip(),
                            "labels": labels,
                            "stats": ath_entry.get("stats") or [],
                        }
        return None

    def fetch_player_live_or_latest_game(
        self,
        player_info: dict,
        prefer_previous_day: bool = False,
        now_pacific: datetime | None = None,
    ) -> dict | None:
        """
        根據美西時間檢查目標日之 ESPN Scoreboard 與 Game Summary Boxscore，
        取得該球員當日進行中 (LIVE) 或已完賽 (FINAL) 的即時比賽數據。
        """
        if not isinstance(player_info, dict):
            return None

        pac_tz = pytz.timezone("US/Pacific")
        if now_pacific is None:
            target_dt = datetime.now(pac_tz)
        elif now_pacific.tzinfo is None:
            target_dt = pac_tz.localize(now_pacific)
        else:
            target_dt = now_pacific.astimezone(pac_tz)

        if prefer_previous_day:
            target_dt = target_dt - timedelta(days=1)

        date_yyyymmdd = target_dt.strftime("%Y%m%d")
        game_date_str = target_dt.strftime("%Y-%m-%d")

        team_id = str(player_info.get("team_id") or "").strip()
        team_abbr = str(player_info.get("team_abbr") or "").strip().upper()

        notice_banner: str | None = None
        matched_event_id: str = ""
        scoreboard = self._fetch_scoreboard(date_yyyymmdd)
        for event in scoreboard.get("events") or []:
            comp = self._match_team_in_event(event, team_id, team_abbr)
            if not comp:
                continue

            event_id = str(event.get("id") or "").strip()
            matched_event_id = event_id
            state, status_label = self._build_status_label(comp, event)
            score_text = self._build_score_text(comp)

            if state in ("in", "post") and event_id:
                summary = self._fetch_summary(event_id)
                box_entry = self._extract_player_from_boxscore(summary, player_info)
                if box_entry and not box_entry["did_not_play"] and box_entry["stats"]:
                    raw_map = dict(zip(box_entry["labels"], box_entry["stats"]))
                    computed = self.compute_fantasy_stats_from_raw(raw_map)
                    return {
                        "event_id": event_id,
                        "game_date": game_date_str,
                        "game_state": state,
                        "status_label": status_label,
                        "score_text": score_text,
                        "minutes": computed.get("MIN", "0"),
                        "stats": computed,
                        "notice_banner": None,
                    }
                reason = box_entry["reason"] if box_entry and box_entry.get("reason") else "DNP"
                notice_banner = f"⚠️ 今日未出賽 ({reason}) • 以下為最近出賽"
                break

            if state == "pre":
                detail = status_label or "Scheduled"
                notice_banner = f"🕒 今日賽事尚未開打 ({detail}) • 以下為最近出賽"
                break

        gamelog_data = self._fetch_gamelog(str(player_info.get("athlete_id") or "").strip())
        return self._extract_latest_game_from_gamelog(
            gamelog_data,
            player_info,
            max_date_str=game_date_str,
            exclude_event_id=matched_event_id,
            notice_banner=notice_banner,
        )

