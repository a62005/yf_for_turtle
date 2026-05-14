# src/fetcher.py
import yahoofantasy

class YahooFantasyFetcher:
    def __init__(self):
        self.ctx = yahoofantasy.Context()
        
    def fetch_league_data(self, league_id: str) -> dict:
        # Ensure league_id has the correct prefix for NBA
        if not league_id.startswith('nba.l.'):
            league_id = f"nba.l.{league_id}"
            
        league = yahoofantasy.League(self.ctx, league_id)
        teams_data = []
        
        for team in league.teams():
            team_info = {
                "name": str(getattr(team, "name", "Unknown")),
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
