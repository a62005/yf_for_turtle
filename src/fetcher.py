import yahoofantasy
from src.constants.stat_map import translate_stat_id
from yahoofantasy.api.parse import as_list, from_response_object
from yahoofantasy.resources.team import Team

class YahooFantasyFetcher:
    def __init__(self, team_mapping: dict = None):
        self.ctx = yahoofantasy.Context()
        self.team_mapping = team_mapping or {}
        
    def fetch_league_data(self, league_id: str) -> dict:
        # Ensure league_id has the correct prefix for NBA
        if not league_id.startswith('nba.l.'):
            league_id = f"nba.l.{league_id}"
            
        league = yahoofantasy.League(self.ctx, league_id)
        teams_data = []
        
        for team in league.teams():
            # Get team ID safely
            team_id = str(getattr(team, "team_id", ""))
            # Use custom name if mapped, else fallback to API name
            team_name = self.team_mapping.get(team_id, str(getattr(team, "name", "Unknown")))
            
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

    def _parse_stats(self, team_obj) -> dict:
        """Extract and translate stats from a team object (standings or scoreboard)."""
        stats_dict = {}
        # Try team_standings
        standings = getattr(team_obj, "team_standings", None)
        if standings:
            for attr in dir(standings):
                if not attr.startswith('_') and not callable(getattr(standings, attr)):
                    val = getattr(standings, attr)
                    if hasattr(val, '__dict__') or (hasattr(val, 'ctx') and hasattr(val, 'id')):
                        for sub_attr in dir(val):
                            if not sub_attr.startswith('_') and not callable(getattr(val, sub_attr)):
                                stats_dict[f"{attr}_{sub_attr}"] = getattr(val, sub_attr)
                    else:
                        stats_dict[attr] = val
        
        # Try team_stats
        tstats = getattr(team_obj, "team_stats", None)
        if tstats and hasattr(tstats, 'stats'):
            try:
                for s in tstats.stats:
                    s_id = getattr(s, 'stat_id', None)
                    s_val = getattr(s, 'value', None)
                    if s_id is not None:
                        label = translate_stat_id(s_id)
                        stats_dict[label] = s_val
            except Exception:
                pass
        return stats_dict

    def fetch_team_stats(self, league_id: str) -> dict:
        if not league_id.startswith('nba.l.'):
            league_id = f"nba.l.{league_id}"
            
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
        if not league_id.startswith('nba.l.'): league_id = f"nba.l.{league_id}"
        league = yahoofantasy.League(self.ctx, league_id)
        # scoreboard;week=N
        data = self.ctx._load_or_fetch(f"weekly_stats.{league_id}.{week}", f"scoreboard;week={week}", league=league_id)
        return self._parse_scoreboard(data)

    def fetch_daily_stats(self, league_id: str, date_str: str) -> dict:
        if not league_id.startswith('nba.l.'): league_id = f"nba.l.{league_id}"
        league = yahoofantasy.League(self.ctx, league_id)
        # scoreboard;type=day;date=YYYY-MM-DD
        data = self.ctx._load_or_fetch(f"daily_stats.{league_id}.{date_str}", f"scoreboard;type=day;date={date_str}", league=league_id)
        return self._parse_scoreboard(data)

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
