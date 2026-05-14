# src/fetcher.py
import yahoofantasy

class YahooFantasyFetcher:
    def __init__(self):
        self.ctx = yahoofantasy.Context()
        
    def fetch_league_data(self, league_id: str) -> dict:
        league = self.ctx.get_league(league_id)
        teams_data = []
        
        for team in league.teams():
            team_info = {
                "name": getattr(team, "name", "Unknown"),
                "roster": []
            }
            
            for player in team.roster():
                player_info = {
                    "name": getattr(player, "name", "Unknown")
                }
                # To extend in the future: fetch stats for each player
                team_info["roster"].append(player_info)
                
            teams_data.append(team_info)
            
        return {"teams": teams_data}
