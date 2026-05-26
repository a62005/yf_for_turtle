import yahoofantasy
import logging
import xml.etree.ElementTree as ET
from src.constants.stat_map import translate_stat_id
from yahoofantasy.api.parse import as_list, from_response_object
from yahoofantasy.resources.team import Team

YAHOO_NS = {'ns': 'http://fantasysports.yahooapis.com/fantasy/v2/base.rng'}

class YahooFantasyFetcher:
    NON_STARTING_POSITIONS = ['BN', 'IL', 'IL+', 'NA']

    def __init__(self, team_mapping: dict = None, client_id: str = None, client_secret: str = None):
        self.ctx = yahoofantasy.Context(
            persist_key="credentials/",
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
                            label = translate_stat_id(s_id)
                            stats_dict[label] = self._get_val(s_val)
                except Exception:
                    pass
        return stats_dict

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

    def fetch_weekly_stats(self, league_id: str, week: int) -> dict:
        league_id = self._normalize_league_id(league_id)
        league = yahoofantasy.League(self.ctx, league_id)
        # Using teams/stats;type=week;week=N to get all 12 teams instead of scoreboard (which only shows matchups)
        url = f"teams/stats;type=week;week={week}"
        data = self.ctx._load_or_fetch(f"weekly_teams_stats.{league_id}.{week}", url, league=league_id)
        return self._parse_teams_from_content(data)

    def fetch_daily_stats(self, league_id: str, date_str: str) -> dict:
        league_id = self._normalize_league_id(league_id)
        league = yahoofantasy.League(self.ctx, league_id)
        # Using teams/stats;type=date;date=YYYY-MM-DD for true daily totals
        url = f"teams/stats;type=date;date={date_str}"
        data = self.ctx._load_or_fetch(f"daily_stats.{league_id}.{date_str}", url, league=league_id)
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

