import os
import json
import pytest
from src.fetcher import YahooFantasyFetcher

@pytest.fixture(autouse=True)
def mock_fetcher_fs(monkeypatch, tmp_path):
    monkeypatch.setattr("src.fetcher.get_league_weekly_dir", lambda *args: str(tmp_path / "weekly"))
    monkeypatch.setattr("src.fetcher.get_league_daily_dir", lambda *args: str(tmp_path / "daily"))

class MockPlayer:
    def __init__(self, name):
        self.name = name

class MockRoster:
    def __init__(self):
        self.players = [MockPlayer("Player 1"), MockPlayer("Player 2")]

class MockTeam:
    def __init__(self, team_name, team_id=1):
        self.name = team_name
        self.team_id = team_id
        # Add mock standings/stats
        self.team_standings = type('Standings', (), {'points_for': 100, 'points_against': 90})()
        # Add team_stats with stat_id for Task 4
        mock_stat = type('Stat', (), {'stat_id': '12', 'value': '50'})()
        mock_stats_obj = type('StatsObj', (), {'stat': [mock_stat]})()
        self.team_stats = type('TeamStats', (), {'stats': mock_stats_obj})()
    
    def roster(self):
        return MockRoster()

class MockLeague:
    def teams(self):
        return [MockTeam("Team A", 1), MockTeam("Team B", 2)]
    def standings(self):
        return self.teams()

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
    
    fetcher = YahooFantasyFetcher(team_mapping={"1": "A01"})
    stats_data = fetcher.fetch_team_stats("mock_league_id")
    
    assert "team_stats" in stats_data
    assert len(stats_data["team_stats"]) == 2
    assert stats_data["team_stats"][0]["name"] == "A01"
    # Verify stats extraction and translation (12 -> PTS)
    assert stats_data["team_stats"][0]["stats"].get("points_for") == 100
    assert stats_data["team_stats"][0]["stats"].get("PTS") == "50"

def test_fetch_weekly_stats(mocker):
    mock_ctx = mocker.patch("src.fetcher.yahoofantasy.Context").return_value
    mocker.patch("src.fetcher.yahoofantasy.League")
    
    # Mock _load_or_fetch data
    teams_data = {
        "fantasy_content": {
            "league": {
                "teams": {
                    "team": [
                        {"team_id": "1", "name": "Team 1"},
                        {"team_id": "2", "name": "Team 2"}
                    ]
                }
            }
        }
    }
    mock_ctx.make_request.return_value = teams_data
    
    # Mock Team and as_list/from_response_object
    mocker.patch("yahoofantasy.resources.team.Team")
    mocker.patch("yahoofantasy.api.parse.as_list", side_effect=lambda x: x if isinstance(x, list) else [x])
    
    def from_response_object_side_effect(obj, data):
        obj.name = data.get("name")
        obj.team_id = data.get("team_id")
    mocker.patch("yahoofantasy.api.parse.from_response_object", side_effect=from_response_object_side_effect)
    
    fetcher = YahooFantasyFetcher(team_mapping={"1": "A01"})
    # Mock _parse_stats to return simple dict
    mocker.patch.object(YahooFantasyFetcher, "_parse_stats", return_value={"PTS": "100"})
    
    data = fetcher.fetch_weekly_stats("12345", 1)
    
    assert "team_stats" in data
    assert len(data["team_stats"]) == 2
    assert data["team_stats"][0]["name"] == "A01"
    assert data["team_stats"][1]["name"] == "Team 2"
    assert data["team_stats"][0]["stats"]["PTS"] == "100"

def test_fetch_daily_stats(mocker):
    mock_ctx = mocker.patch("src.fetcher.yahoofantasy.Context").return_value
    mocker.patch("src.fetcher.yahoofantasy.League")
    
    teams_data = {
        "fantasy_content": {
            "league": {
                "teams": {
                    "team": [
                        {"team_id": "1", "name": "Team 1"}
                    ]
                }
            }
        }
    }
    mock_ctx.make_request.return_value = teams_data

    
    mocker.patch("yahoofantasy.resources.team.Team")
    mocker.patch("yahoofantasy.api.parse.as_list", side_effect=lambda x: x if isinstance(x, list) else [x])
    
    def from_response_object_side_effect(obj, data):
        obj.name = data.get("name")
        obj.team_id = data.get("team_id")
    mocker.patch("yahoofantasy.api.parse.from_response_object", side_effect=from_response_object_side_effect)
    
    fetcher = YahooFantasyFetcher()
    mocker.patch.object(YahooFantasyFetcher, "_parse_stats", return_value={"PTS": "20"})
    
    data = fetcher.fetch_daily_stats("12345", "2023-11-01")
    
    assert "team_stats" in data
    assert len(data["team_stats"]) == 1
    assert data["team_stats"][0]["stats"]["PTS"] == "20"

def test_fetch_batch_rosters(mocker):
    mock_ctx = mocker.patch("src.fetcher.yahoofantasy.Context").return_value
    xml_response = """
    <fantasy_content xmlns="http://fantasysports.yahooapis.com/fantasy/v2/base.rng">
      <league>
        <teams>
          <team>
            <team_id>1</team_id>
            <roster>
              <players>
                <player>
                  <selected_position><position>PG</position></selected_position>
                </player>
                <player>
                  <selected_position><position>BN</position></selected_position>
                </player>
              </players>
            </roster>
          </team>
        </teams>
      </league>
    </fantasy_content>
    """
    mock_ctx.make_request.return_value = xml_response
    
    fetcher = YahooFantasyFetcher()
    data = fetcher.fetch_batch_rosters("12345", "2023-11-01")
    
    assert data == {"1": 1}

def test_fetch_league_scoreboard(mocker):
    mock_ctx = mocker.patch("src.fetcher.yahoofantasy.Context").return_value
    xml_response = """
    <fantasy_content xmlns="http://fantasysports.yahooapis.com/fantasy/v2/base.rng">
      <league>
        <scoreboard>
          <matchups>
            <matchup>
              <teams>
                <team>
                  <team_id>1</team_id>
                  <team_remaining_games>
                    <total>
                      <completed_games>2</completed_games>
                      <live_games>1</live_games>
                      <remaining_games>3</remaining_games>
                    </total>
                  </team_remaining_games>
                </team>
                <team>
                  <team_id>2</team_id>
                  <team_remaining_games>
                    <total>
                      <completed_games>1</completed_games>
                      <live_games>0</live_games>
                      <remaining_games>4</remaining_games>
                    </total>
                  </team_remaining_games>
                </team>
              </teams>
            </matchup>
          </matchups>
        </scoreboard>
      </league>
    </fantasy_content>
    """
    mock_ctx.make_request.return_value = xml_response
    
    fetcher = YahooFantasyFetcher()
    data = fetcher.fetch_league_scoreboard("12345", 1)
    
    assert data == {
        "1": {"played": 3, "total": 6},
        "2": {"played": 1, "total": 5}
    }

def test_fetch_week_end_date(mocker):
    from src.fetcher import YahooFantasyFetcher
    mock_ctx = mocker.patch("yahoofantasy.Context")
    
    mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <fantasy_content xml:lang="en-US" yahoo:uri="http://fantasysports.yahooapis.com/fantasy/v2/league/12345/scoreboard;week=16" xmlns:yahoo="http://www.yahooapis.com/v1/base.rng" xmlns="http://fantasysports.yahooapis.com/fantasy/v2/base.rng">
      <league>
        <scoreboard>
          <matchups>
            <matchup>
              <week>16</week>
              <week_start>2025-02-03</week_start>
              <week_end>2025-02-09</week_end>
            </matchup>
          </matchups>
        </scoreboard>
      </league>
    </fantasy_content>
    """
    mock_ctx.return_value.make_request.return_value = mock_xml
    
    fetcher = YahooFantasyFetcher("12345")
    fetcher.ctx = mock_ctx.return_value
    
    # Assert successful parsing
    end_date = fetcher.fetch_week_end_date("12345", 16)
    assert end_date == "2025-02-09"
    
    # Test error handling (missing matchup)
    mock_error_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <fantasy_content xmlns="http://fantasysports.yahooapis.com/fantasy/v2/base.rng">
      <league><scoreboard><matchups></matchups></scoreboard></league>
    </fantasy_content>"""
    mock_ctx.return_value.make_request.return_value = mock_error_xml
    end_date_err = fetcher.fetch_week_end_date("12345", 16)
    assert end_date_err is None


def test_fetch_league_metadata_permission_denied(mocker):
    from src.fetcher import LeaguePermissionError
    
    mock_ctx = mocker.patch("src.fetcher.yahoofantasy.Context")
    mock_ctx.return_value.make_request.side_effect = Exception("HTTP Error 403 Forbidden")
    
    fetcher = YahooFantasyFetcher()
    fetcher.ctx = mock_ctx.return_value
    
    with pytest.raises(LeaguePermissionError):
        fetcher.fetch_league_metadata("12345")

    mock_league = mocker.patch("src.fetcher.yahoofantasy.League")
    mock_league.return_value.teams.side_effect = Exception("HTTP Error 401 Unauthorized")
    
    with pytest.raises(LeaguePermissionError):
        fetcher.fetch_league_data("12345")

