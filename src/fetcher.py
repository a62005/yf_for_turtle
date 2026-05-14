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
        
        for team in league.teams():
            team_id = str(getattr(team, "team_id", ""))
            team_name = self.team_mapping.get(team_id, str(getattr(team, "name", "Unknown")))
            
            # Attempt to safely extract some stats, depending on yahoofantasy model
            stats_dict = {}
            standings = getattr(team, "team_standings", None)
            if standings:
                # Extract simple numeric/string attributes
                for attr in dir(standings):
                    if not attr.startswith('_') and not callable(getattr(standings, attr)):
                        stats_dict[attr] = getattr(standings, attr)
                        
            # Also try team.team_stats or team.stats if available
            team_stats = getattr(team, "team_stats", None) or getattr(team, "stats", None)
            if team_stats and hasattr(team_stats, 'stats'):
                # Assuming yahoofantasy's team_stats.stats is a list of Stat objects or dict
                stats_dict['detailed_stats'] = str(team_stats.stats)

            team_stats_data.append({
                "name": team_name,
                "stats": stats_dict
            })
            
        return {"team_stats": team_stats_data}
