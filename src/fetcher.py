import yahoofantasy
import logging
import xml.etree.ElementTree as ET
import os
import json
import shutil
from src.utils.path_utils import get_league_weekly_dir, get_league_daily_dir
from src.constants.stat_map import translate_stat_id
from yahoofantasy.api.parse import as_list, from_response_object, parse_response
from yahoofantasy.resources.team import Team


YAHOO_NS = {'ns': 'http://fantasysports.yahooapis.com/fantasy/v2/base.rng'}

class LeaguePermissionError(Exception):
    """Raised when the robot has no permission to access the Yahoo league."""
    pass

def handle_permission_errors(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            err_str = str(e)
            if "401" in err_str or "403" in err_str:
                raise LeaguePermissionError(f"Yahoo API Permission Denied (401/403): {e}") from e
            raise
    return wrapper

_real_exists = os.path.exists

class YahooFantasyFetcher:
    NON_STARTING_POSITIONS = ['BN', 'IL', 'IL+', 'NA']

    def __init__(self, team_mapping: dict = None, client_id: str = None, client_secret: str = None, league_id: str = None):
        if league_id is None:
            from src.config import load_config
            league_id = load_config().get("LEAGUE_ID")
        self.league_id = league_id

        persist_key = "credentials/"
        if league_id:
            from src.utils.path_utils import BASE_DIR, get_league_dir
            league_dir = get_league_dir(league_id)
            
            # 1. 處理憑證的複製繼承
            spec_oauth_path = os.path.join(league_dir, "oauth2.json")
            global_oauth_path = os.path.join(BASE_DIR, "credentials", "oauth2.json")
            if not _real_exists(spec_oauth_path) and _real_exists(global_oauth_path):
                os.makedirs(league_dir, exist_ok=True)
                shutil.copy2(global_oauth_path, spec_oauth_path)
            
            spec_yf_path = os.path.join(league_dir, ".yahoofantasy")
            global_yf_path = os.path.join(BASE_DIR, "credentials", ".yahoofantasy")
            if not _real_exists(spec_yf_path) and _real_exists(global_yf_path):
                os.makedirs(league_dir, exist_ok=True)
                shutil.copy2(global_yf_path, spec_yf_path)
                
            lid_str = str(league_id)
            if lid_str.startswith("nba.l."):
                sport = "nba"
                raw_id = lid_str.split(".")[-1]
            elif lid_str.startswith("mlb.l."):
                sport = "mlb"
                raw_id = lid_str.split(".")[-1]
            elif "." in lid_str:
                parts = lid_str.split(".")
                sport = parts[0]
                raw_id = parts[-1]
            else:
                sport = "nba"
                raw_id = lid_str
            persist_key = f"data/league/{sport}/{raw_id}/"

        self.ctx = yahoofantasy.Context(
            persist_key=persist_key,
            client_id=client_id,
            client_secret=client_secret
        )
        self.team_mapping = team_mapping or {}

    def _normalize_league_id(self, league_id: str) -> str:
        if league_id and not str(league_id).startswith('nba.l.'):
            return f"nba.l.{league_id}"
        return str(league_id)
        
    def _find_node(self, parent, path):
        return parent.find(path, YAHOO_NS)

    def _find_all_nodes(self, parent, path):
        return parent.findall(path, YAHOO_NS)

    @handle_permission_errors
    def sync_league_settings(self, league_id: str) -> list:
        """Fetch league settings and parse all stats categories with sort orders."""
        league_id = self._normalize_league_id(league_id)
        url = f"league/{league_id}/settings"
        xml_data = self.ctx.make_request(url)
        root = ET.fromstring(xml_data)
        
        stats = []
        stat_nodes = root.findall('.//ns:stat_categories/ns:stats/ns:stat', YAHOO_NS)
        for node in stat_nodes:
            s_id_node = node.find('ns:stat_id', YAHOO_NS)
            name_node = node.find('ns:name', YAHOO_NS)
            disp_node = node.find('ns:display_name', YAHOO_NS)
            sort_node = node.find('ns:sort_order', YAHOO_NS)
            
            s_id = s_id_node.text if s_id_node is not None else None
            disp = disp_node.text if disp_node is not None else (name_node.text if name_node is not None else "")
            sort_val = int(sort_node.text) if (sort_node is not None and sort_node.text is not None) else 1
            
            if s_id:
                stats.append({
                    "stat_id": str(s_id),
                    "display_name": str(disp),
                    "sort_order": sort_val
                })
                
        # Cache it in metadata.json
        from src.utils.path_utils import get_league_dir
        meta_path = os.path.join(get_league_dir(league_id), "metadata.json")
        meta = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                pass
        meta["stat_categories"] = stats
        os.makedirs(os.path.dirname(meta_path), exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
            
        return stats

    def _get_stat_map(self, league_id: str = None) -> dict:
        if not league_id:
            pk = getattr(self.ctx, "_persist_key", "")
            parts = [p for p in pk.split("/") if p]
            if len(parts) >= 4 and parts[1] == "league":
                league_id = f"{parts[2]}.l.{parts[3]}"
                
        if not league_id:
            league_id = getattr(self, "league_id", None)
        if not league_id:
            from src.config import load_config
            league_id = load_config().get("LEAGUE_ID")
            
        from src.utils.path_utils import get_league_dir
        meta_path = os.path.join(get_league_dir(league_id), "metadata.json")
        stat_map = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    for cat in meta.get("stat_categories", []):
                        stat_map[str(cat["stat_id"])] = cat["display_name"]
            except Exception:
                pass
        
        if not stat_map:
            from src.constants.stat_map import STAT_MAP
            stat_map = STAT_MAP
        return stat_map

    def _translate_stat(self, s_id, league_id=None) -> str:
        stat_map = self._get_stat_map(league_id)
        s_id_str = str(s_id)
        return stat_map.get(s_id_str, f"stat_{s_id_str}")

    @handle_permission_errors
    def fetch_league_metadata(self, league_id: str) -> dict:
        """Fetch basic league metadata including season start and end dates."""
        league_id = self._normalize_league_id(league_id)
        url = f"league/{league_id}"
        
        try:
            import xml.etree.ElementTree as ET
            data = self.ctx.make_request(url)
            root = ET.fromstring(data)
            
            # The namespace handling for Yahoo Fantasy XML
            ns = {'ns': 'http://fantasysports.yahooapis.com/fantasy/v2/base.rng'}
            league_node = root.find('ns:league', ns)
            
            if league_node is not None:
                start_date_node = league_node.find('ns:start_date', ns)
                end_date_node = league_node.find('ns:end_date', ns)
                season_node = league_node.find('ns:season', ns)
                name_node = league_node.find('ns:name', ns)
                end_week_node = league_node.find('ns:end_week', ns)
                
                start_date = start_date_node.text if start_date_node is not None else None
                end_date = end_date_node.text if end_date_node is not None else None
                season = season_node.text if season_node is not None else None
                name = name_node.text if name_node is not None else "Unknown League"
                end_week = end_week_node.text if end_week_node is not None else None
            else:
                start_date, end_date, season, name, end_week = None, None, None, "Unknown League", None
                
        except Exception as e:
            # 權限不足的錯誤應立即拋出，不進行 fallback
            err_str = str(e)
            if "401" in err_str or "403" in err_str:
                raise
            # Fallback if XML parsing fails
            import logging
            logging.error(f"Failed to parse league metadata XML: {e}")
            league = yahoofantasy.League(self.ctx, league_id)
            start_date = getattr(league, "start_date", None)
            end_date = getattr(league, "end_date", None)
            name = getattr(league, "name", "Unknown League")
            season = getattr(league, "season", None)
            end_week = getattr(league, "end_week", None)

        return {
            "league_id": league_id,
            "name": name,
            "season": season,
            "start_date": str(start_date) if start_date else None,
            "end_date": str(end_date) if end_date else None,
            "end_week": int(end_week) if end_week else None
        }

    def fetch_week_end_date(self, league_id: str, week: int) -> str | None:
        """Fetch the end date for a specific week from the scoreboard."""
        league_id = self._normalize_league_id(league_id)
        url = f"league/{league_id}/scoreboard;week={week}"
        try:
            import xml.etree.ElementTree as ET
            import logging
            data = self.ctx.make_request(url)
            root = ET.fromstring(data)
            ns = {'ns': 'http://fantasysports.yahooapis.com/fantasy/v2/base.rng'}
            matchup_node = root.find('.//ns:matchups/ns:matchup', ns)
            if matchup_node is not None:
                end_node = matchup_node.find('ns:week_end', ns)
                if end_node is not None:
                    return end_node.text
            return None
        except Exception as e:
            import logging
            logging.error(f"Failed to fetch week end date for week {week}: {e}")
            return None

    @handle_permission_errors
    def fetch_league_data(self, league_id: str) -> dict:
        # Ensure league_id has the correct prefix for NBA
        league_id = self._normalize_league_id(league_id)
            
        league = yahoofantasy.League(self.ctx, league_id)
        teams_data = []
        
        for team in league.teams():
            # Get team ID safely
            team_id = str(getattr(team, "team_id", ""))
            # Use custom name if mapped, else fallback to API name
            team_name = self.get_team_name(team_id, str(getattr(team, "name", "Unknown")))
            
            team_info = {
                "name": team_name,
                "roster": []
            }
            
            for player in team.roster().players:
                player_info = {
                    "name": str(getattr(player, "name", "Unknown"))
                }
                # To extend in the future: fetch stats for each player
                team_info["roster"].append(player_info)
                
            teams_data.append(team_info)
            
        return {"teams": teams_data}

    def get_team_name(self, team_id: str, default_name: str = "Unknown") -> str:
        return self.team_mapping.get(str(team_id), default_name)

    def _get_val(self, obj):
        """Helper to get a serializable value from a Yahoo API object."""
        if hasattr(obj, "$"):
            return getattr(obj, "$")
        if hasattr(obj, "__dict__"):
            # If it's a complex object, we might want to return it as a dict or just its string representation
            # For stats, usually they are simple values under the attribute
            return str(obj)
        return obj

    def _parse_stats(self, team_obj) -> dict:
        """Extract and translate stats from a team object (standings or scoreboard)."""
        stats_dict = {}
        # Try team_standings
        standings = getattr(team_obj, "team_standings", None)
        if standings:
            for attr in dir(standings):
                if not attr.startswith('_') and not callable(getattr(standings, attr)):
                    val = getattr(standings, attr)
                    # Handle nested objects like outcome_totals
                    if hasattr(val, 'outcome_totals') or hasattr(val, 'wins'):
                         for sub_attr in dir(val):
                            if not sub_attr.startswith('_') and not callable(getattr(val, sub_attr)):
                                stats_dict[f"{attr}_{sub_attr}"] = self._get_val(getattr(val, sub_attr))
                    else:
                        stats_dict[attr] = self._get_val(val)
        
        # Try team_stats
        tstats = getattr(team_obj, "team_stats", None)
        if tstats:
            if hasattr(tstats, 'stats'):
                try:
                    stat_list = getattr(tstats.stats, 'stat', [])
                    for s in as_list(stat_list):
                        s_id = getattr(s, 'stat_id', None)
                        s_val = getattr(s, 'value', None)
                        if s_id is not None:
                            label = self._translate_stat(s_id)
                            stats_dict[label] = self._get_val(s_val)
                except Exception:
                    pass
        return stats_dict

    @handle_permission_errors
    def fetch_team_stats(self, league_id: str) -> dict:
        league_id = self._normalize_league_id(league_id)
            
        league = yahoofantasy.League(self.ctx, league_id)
        team_stats_data = []
        
        # Use league.standings() as it often contains more data than league.teams()
        try:
            teams_from_standings = league.standings()
        except Exception:
            teams_from_standings = league.teams()
            
        for team in teams_from_standings:
            team_id = str(getattr(team, "team_id", ""))
            team_name = self.team_mapping.get(team_id, str(getattr(team, "name", "Unknown")))
            
            stats_dict = self._parse_stats(team)

            team_stats_data.append({
                "name": team_name,
                "stats": stats_dict
            })
            
        return {"team_stats": team_stats_data}

    @handle_permission_errors
    def fetch_weekly_stats(self, league_id: str, week: int) -> dict:
        league_id = self._normalize_league_id(league_id)
        raw_id = league_id.split(".")[-1]
        
        cache_dir = get_league_weekly_dir(raw_id)
        cache_path = os.path.join(cache_dir, f"week_{week}.json")
        
        if os.path.exists(cache_path):
            logging.info(f"[CACHE] 命中週數據快取: {cache_path}")
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data:
                    return self._parse_teams_from_content(data)
            except Exception as e:
                logging.warning(f"[CACHE] 讀取週數據快取失敗: {e}")
                
        url = f"league/{league_id}/scoreboard;week={week}"
        data_raw = self.ctx.make_request(url)
        data = parse_response(data_raw) if isinstance(data_raw, str) else data_raw
        
        os.makedirs(cache_dir, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return self._parse_teams_from_content(data)

    @handle_permission_errors
    def fetch_daily_stats(self, league_id: str, date_str: str) -> dict:
        league_id = self._normalize_league_id(league_id)
        raw_id = league_id.split(".")[-1]
        
        cache_dir = get_league_daily_dir(raw_id)
        cache_path = os.path.join(cache_dir, f"date_{date_str}.json")
        
        if os.path.exists(cache_path):
            logging.info(f"[CACHE] 命中日數據快取: {cache_path}")
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data:
                    return self._parse_teams_from_content(data)
            except Exception as e:
                logging.warning(f"[CACHE] 讀取日數據快取失敗: {e}")
                
        url = f"league/{league_id}/teams/stats;type=date;date={date_str}"
        data_raw = self.ctx.make_request(url)
        data = parse_response(data_raw) if isinstance(data_raw, str) else data_raw
        
        os.makedirs(cache_dir, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return self._parse_teams_from_content(data)


    def _parse_teams_from_content(self, data) -> dict:
        """Common parser for responses containing a list of teams (standings or teams/stats)."""
        team_stats_data = []
        try:
            teams_data = data["fantasy_content"]["league"]["teams"]["team"]
            for team_item in as_list(teams_data):
                t = Team(self.ctx, None, team_item["team_id"])
                from_response_object(t, team_item)
                team_id = str(getattr(t, "team_id", ""))
                team_name = self.get_team_name(team_id, team_item.get("name", "Unknown"))

                stats_dict = self._parse_stats(t)

                # Extract game counts if available (useful for weekly stats)
                if "team_remaining_games" in team_item:
                    try:
                        total_node = team_item["team_remaining_games"]["total"]
                        def get_num(key):
                            val = total_node.get(key, 0)
                            if isinstance(val, dict):
                                return int(val.get("$", 0))
                            return int(val or 0)
                            
                        completed = get_num("completed_games")
                        live = get_num("live_games")
                        remaining = get_num("remaining_games")
                        played = completed + live
                        total = played + remaining
                        stats_dict["GP_PLAYED"] = played
                        stats_dict["GP_TOTAL"] = total
                    except Exception as e:
                        import logging
                        logging.debug(f"Could not parse game counts for team {team_id}: {e}")

                team_stats_data.append({
                    "team_id": team_id,
                    "name": team_name,
                    "stats": stats_dict
                })
        except Exception as e:
            import logging
            logging.error(f"Error parsing teams from content: {e}")
        return {"team_stats": team_stats_data}

    def _parse_scoreboard(self, data) -> dict:
        team_stats_data = []
        try:
            matchups = data["fantasy_content"]["league"]["scoreboard"]["matchups"]["matchup"]
            for matchup in as_list(matchups):
                for team_data in as_list(matchup["teams"]["team"]):
                    t = Team(self.ctx, None, team_data["team_id"])
                    from_response_object(t, team_data)
                    team_id = str(getattr(t, "team_id", ""))
                    team_name = self.team_mapping.get(team_id, str(getattr(t, "name", "Unknown")))
                    team_stats_data.append({
                        "name": team_name,
                        "stats": self._parse_stats(t)
                    })
        except Exception:
            pass
        return {"team_stats": team_stats_data}

    def fetch_batch_rosters(self, league_id: str, date_str: str) -> dict:
        """Fetch non-bench player counts for all teams in the league for a specific date."""
        league_id = self._normalize_league_id(league_id)
        # Fetching rosters for all teams via batch request
        url = f"teams/roster;date={date_str}"
        roster_counts = {}
        try:
            data = self.ctx.make_request(url, league=league_id)
            root = ET.fromstring(data)
            for team in self._find_all_nodes(root, './/ns:team'):
                team_id_node = self._find_node(team, 'ns:team_id')
                if team_id_node is None:
                    continue
                team_id = team_id_node.text
                
                active_count = 0
                for player in self._find_all_nodes(team, './/ns:player'):
                    pos_node = self._find_node(player, './/ns:selected_position/ns:position')
                    pos = pos_node.text if pos_node is not None else None
                    # Non-starting positions to exclude
                    if pos and pos not in self.NON_STARTING_POSITIONS:
                        active_count += 1
                roster_counts[team_id] = active_count
        except Exception as e:
            logging.error(f"Error parsing batch rosters: {e}")
        return roster_counts

    def fetch_league_scoreboard(self, league_id: str, week: int) -> dict:
        """Fetch played and total game counts for all teams from the scoreboard."""
        league_id = self._normalize_league_id(league_id)
        url = f"league/{league_id}/scoreboard;week={week}"
        
        game_counts = {}
        try:
            data = self.ctx.make_request(url)
            root = ET.fromstring(data)
            for team in self._find_all_nodes(root, './/ns:team'):
                team_id_node = self._find_node(team, 'ns:team_id')
                if team_id_node is None:
                    continue
                team_id = team_id_node.text
                
                rem_games_node = self._find_node(team, './/ns:team_remaining_games/ns:total')
                if rem_games_node is not None:
                    def get_int_text(node_path):
                        node = self._find_node(rem_games_node, node_path)
                        if node is not None and node.text:
                            try:
                                return int(node.text)
                            except ValueError:
                                return 0
                        return 0

                    completed = get_int_text('ns:completed_games')
                    live = get_int_text('ns:live_games')
                    remaining = get_int_text('ns:remaining_games')
                    
                    played = completed + live
                    total = played + remaining
                    game_counts[team_id] = {"played": played, "total": total}
        except Exception as e:
            logging.error(f"Error parsing scoreboard games: {e}")
        return game_counts

    def _parse_team_stats_xml(self, xml_data: str) -> dict:
        """解析 Yahoo Team stats XML 並翻譯為 9-Cat 格式"""
        root = ET.fromstring(xml_data)
        
        # 尋找 team 節點與名稱
        team_node = root.find('.//ns:team', YAHOO_NS)
        if team_node is None:
            team_node = root # Fallback
            
        name_node = team_node.find('ns:name', YAHOO_NS)
        team_name = name_node.text if name_node is not None else "Unknown Team"
        
        stats_dict = {}
        stat_nodes = team_node.findall('.//ns:team_stats/ns:stats/ns:stat', YAHOO_NS)
        for node in stat_nodes:
            s_id = node.find('ns:stat_id', YAHOO_NS).text
            s_val = node.find('ns:value', YAHOO_NS).text
            
            label = self._translate_stat(s_id)
            stats_dict[label] = s_val if s_val is not None else "0"
            
        return {
            "team_name": team_name,
            "stats": stats_dict
        }

    @handle_permission_errors
    def fetch_single_team_stats_by_url(self, team_key: str, stat_type: str, type_val: str) -> dict:
        """實時且無快取地抓取單一隊伍在指定日期/週數的 9-Cat 數據"""
        url = f"team/{team_key}/stats;type={stat_type};{stat_type}={type_val}"
        xml_data = self.ctx.make_request(url)
        return self._parse_team_stats_xml(xml_data)

    @handle_permission_errors
    def fetch_matchups(self, league_id: str, week: int) -> list:
        """Fetch matchups with detailed team stats for a specific week from the scoreboard."""
        league_id = self._normalize_league_id(league_id)
        url = f"league/{league_id}/scoreboard;week={week}"
        
        matchups_data = []
        try:
            data = self.ctx.make_request(url)
            root = ET.fromstring(data)
            
            for matchup in self._find_all_nodes(root, './/ns:matchup'):
                teams = []
                for team in self._find_all_nodes(matchup, './/ns:team'):
                    team_id_node = self._find_node(team, 'ns:team_id')
                    if team_id_node is None:
                        continue
                    team_id = team_id_node.text
                    
                    # Name node
                    name_node = self._find_node(team, 'ns:name')
                    official_name = name_node.text if name_node is not None else "Unknown Team"
                    team_name = self.get_team_name(team_id, official_name)
                    
                    # Parse stats
                    stats_dict = {}
                    stat_nodes = self._find_all_nodes(team, './/ns:team_stats/ns:stats/ns:stat')
                    for node in stat_nodes:
                        s_id_node = self._find_node(node, 'ns:stat_id')
                        s_val_node = self._find_node(node, 'ns:value')
                        if s_id_node is not None and s_id_node.text:
                            s_id = s_id_node.text
                            s_val = s_val_node.text if s_val_node is not None else "0"
                            label = self._translate_stat(s_id, league_id)
                            stats_dict[label] = s_val if s_val is not None else "0"
                    
                    # 拼接出手數與分母輔助項
                    if "FGM/FGA" not in stats_dict:
                        fgm = stats_dict.get("stat_4")
                        fga = stats_dict.get("stat_3")
                        if fgm is not None and fga is not None:
                            stats_dict["FGM/FGA"] = f"{fgm}/{fga}" if fga != "0" else "0/0"
                    if "FTM/FTA" not in stats_dict:
                        ftm = stats_dict.get("stat_7")
                        fta = stats_dict.get("stat_6")
                        if ftm is not None and fta is not None:
                            stats_dict["FTM/FTA"] = f"{ftm}/{fta}" if fta != "0" else "0/0"
                    
                    teams.append({
                        "team_id": team_id,
                        "name": team_name,
                        "official_name": official_name,
                        "stats": stats_dict
                    })
                
                if len(teams) == 2:
                    matchups_data.append({
                        "team1": teams[0],
                        "team2": teams[1]
                    })
        except Exception as e:
            logging.error(f"Error parsing matchups: {e}")
        return matchups_data



