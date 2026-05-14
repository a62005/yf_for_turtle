# tests/test_fetcher.py
import pytest
from src.fetcher import YahooFantasyFetcher

class MockPlayer:
    def __init__(self, name):
        self.name = name

class MockRoster:
    def __init__(self):
        self.players = [MockPlayer("Player 1"), MockPlayer("Player 2")]

class MockTeam:
    def __init__(self, name, team_name):
        self.name = team_name
    
    def roster(self):
        return MockRoster()

class MockLeague:
    def teams(self):
        return [MockTeam("Team A", "Team A")]

def test_fetch_league_data(mocker):
    # Mock yahoofantasy Context and League
    mock_ctx = mocker.patch("src.fetcher.yahoofantasy.Context")
    mock_league = mocker.patch("src.fetcher.yahoofantasy.League")
    mock_league.return_value = MockLeague()
    
    fetcher = YahooFantasyFetcher()
    data = fetcher.fetch_league_data("mock_league_id")
    
    assert "teams" in data
    assert len(data["teams"]) == 1
    assert data["teams"][0]["name"] == "Team A"
    assert len(data["teams"][0]["roster"]) == 2
    assert data["teams"][0]["roster"][0]["name"] == "Player 1"
