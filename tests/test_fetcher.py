import os
import json
import pytest
from src.fetcher import YahooFantasyFetcher

class MockPlayer:
    def __init__(self, name):
        self.name = name

class MockRoster:
    def __init__(self):
        self.players = [MockPlayer("Player 1"), MockPlayer("Player 2")]

class MockTeam:
    def __init__(self, name, team_name, team_id=1):
        self.name = team_name
        self.team_id = team_id
        # Add mock standings/stats
        self.team_standings = type('Standings', (), {'points_for': 100, 'points_against': 90})()
    
    def roster(self):
        return MockRoster()

class MockLeague:
    def teams(self):
        return [MockTeam("Team A", "Team A", 1), MockTeam("Team B", "Team B", 2)]

def test_fetch_league_data(mocker):
    # Keep old test functioning but adapted to the new mock
    mocker.patch("src.fetcher.yahoofantasy.Context")
    mock_league = mocker.patch("src.fetcher.yahoofantasy.League")
    mock_league.return_value = MockLeague()
    
    fetcher = YahooFantasyFetcher()
    data = fetcher.fetch_league_data("mock_league_id")
    
    assert "teams" in data
    assert len(data["teams"]) == 2
    assert data["teams"][0]["name"] == "Team A"
    assert len(data["teams"][0]["roster"]) == 2
    assert data["teams"][0]["roster"][0]["name"] == "Player 1"

def test_fetch_league_data_with_mapping(mocker):
    # Mock yahoofantasy Context and League
    mocker.patch("src.fetcher.yahoofantasy.Context")
    mock_league = mocker.patch("src.fetcher.yahoofantasy.League")
    mock_league.return_value = MockLeague()
    
    fetcher = YahooFantasyFetcher(team_mapping={"1": "A01"})
    data = fetcher.fetch_league_data("mock_league_id")
    
    assert "teams" in data
    assert len(data["teams"]) == 2
    # Team 1 should be renamed to A01
    assert data["teams"][0]["name"] == "A01"
    # Team 2 has no mapping, should remain "Team B"
    assert data["teams"][1]["name"] == "Team B"

def test_fetch_team_stats(mocker):
    mocker.patch("src.fetcher.yahoofantasy.Context")
    mock_league = mocker.patch("src.fetcher.yahoofantasy.League")
    mock_league.return_value = MockLeague()
    
    # We use DI now instead of mocking os.path.exists
    fetcher = YahooFantasyFetcher(team_mapping={"1": "A01"})
    stats_data = fetcher.fetch_team_stats("mock_league_id")
    
    assert "team_stats" in stats_data
    assert len(stats_data["team_stats"]) == 2
    assert stats_data["team_stats"][0]["name"] == "A01"
    # Verify stats extraction
    assert stats_data["team_stats"][0]["stats"].get("points_for") == 100
