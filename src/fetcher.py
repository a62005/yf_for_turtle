import yahoofantasy

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
            
            stats_dict = {}
            
            # 1. Extract from team_standings
            standings = getattr(team, "team_standings", None)
            if standings:
                for attr in dir(standings):
                    if not attr.startswith('_') and not callable(getattr(standings, attr)):
                        val = getattr(standings, attr)
                        # Handle nested objects like outcome_totals
                        if hasattr(val, '__dict__') or (hasattr(val, 'ctx') and hasattr(val, 'id')):
                            for sub_attr in dir(val):
                                if not sub_attr.startswith('_') and not callable(getattr(val, sub_attr)):
                                    stats_dict[f"{attr}_{sub_attr}"] = getattr(val, sub_attr)
                        else:
                            stats_dict[attr] = val
                        
            # 2. Extract from team_stats
            tstats = getattr(team, "team_stats", None)
            if tstats and hasattr(tstats, 'stats'):
                # In some versions, stats is a list of objects with stat_id and value
                try:
                    for s in tstats.stats:
                        s_id = getattr(s, 'stat_id', None)
                        s_val = getattr(s, 'value', None)
                        if s_id is not None:
                            stats_dict[f"stat_{s_id}"] = s_val
                except Exception:
                    stats_dict['raw_stats'] = str(tstats.stats)

            team_stats_data.append({
                "name": team_name,
                "stats": stats_dict
            })
            
        return {"team_stats": team_stats_data}
