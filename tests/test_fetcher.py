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
    
    # Mock os.path.exists and json.load for team_mapping.json
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("builtins.open", mocker.mock_open(read_data='{"1": "A01"}'))
    
    fetcher = YahooFantasyFetcher()
    data = fetcher.fetch_league_data("mock_league_id")
    
    assert "teams" in data
    assert len(data["teams"]) == 2
    # Team 1 should be renamed to A01
    assert data["teams"][0]["name"] == "A01"
    # Team 2 has no mapping, should remain "Team B"
    assert data["teams"][1]["name"] == "Team B"
