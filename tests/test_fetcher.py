# tests/test_fetcher.py
import pytest
from src.fetcher import YahooFantasyFetcher

class MockPlayer:
    def __init__(self, name):
        self.name = name

class MockTeam:
    def __init__(self, name, team_name):
        self.name = team_name
    
    def roster(self):
        return [MockPlayer("Player 1"), MockPlayer("Player 2")]

class MockLeague:
    def teams(self):
        return [MockTeam("Team A", "Team A")]

def test_fetch_league_data(mocker):
    # Mock yahoofantasy Context
    mock_ctx = mocker.patch("src.fetcher.yahoofantasy.Context")
    mock_ctx.return_value.get_league.return_value = MockLeague()
    
    fetcher = YahooFantasyFetcher()
    data = fetcher.fetch_league_data("mock_league_id")
    
    assert "teams" in data
    assert len(data["teams"]) == 1
    assert data["teams"][0]["name"] == "Team A"
    assert len(data["teams"][0]["roster"]) == 2
    assert data["teams"][0]["roster"][0]["name"] == "Player 1"
