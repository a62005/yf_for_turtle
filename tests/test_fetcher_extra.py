import os
import pytest
from src.fetcher import YahooFantasyFetcher

def test_fetch_league_metadata_xml_success(mocker):
    mock_ctx = mocker.patch("src.fetcher.yahoofantasy.Context").return_value
    xml_response = """
    <fantasy_content xmlns="http://fantasysports.yahooapis.com/fantasy/v2/base.rng">
      <league>
        <name>Test League</name>
        <season>2025</season>
        <start_date>2025-10-21</start_date>
        <end_date>2026-04-05</end_date>
        <end_week>23</end_week>
      </league>
    </fantasy_content>
    """
    mock_ctx.make_request.return_value = xml_response
    
    fetcher = YahooFantasyFetcher()
    data = fetcher.fetch_league_metadata("12345")
    
    assert data["name"] == "Test League"
    assert data["season"] == "2025"
    assert data["start_date"] == "2025-10-21"
    assert data["end_date"] == "2026-04-05"
    assert data["end_week"] == 23

def test_fetch_league_metadata_xml_missing_fields(mocker):
    mock_ctx = mocker.patch("src.fetcher.yahoofantasy.Context").return_value
    xml_response = """
    <fantasy_content xmlns="http://fantasysports.yahooapis.com/fantasy/v2/base.rng">
      <league>
      </league>
    </fantasy_content>
    """
    mock_ctx.make_request.return_value = xml_response
    
    fetcher = YahooFantasyFetcher()
    data = fetcher.fetch_league_metadata("12345")
    
    assert data["name"] == "Unknown League"
    assert data["season"] is None
    assert data["start_date"] is None
    assert data["end_date"] is None
    assert data["end_week"] is None

def test_fetch_league_metadata_fallback(mocker):
    mock_ctx = mocker.patch("src.fetcher.yahoofantasy.Context").return_value
    mock_ctx.make_request.side_effect = Exception("API Error")
    
    # Mock fallback yahoofantasy.League
    class MockFallbackLeague:
        def __init__(self, ctx, lid):
            self.name = "Fallback League"
            self.start_date = "2024-01-01"
            self.end_date = "2024-05-01"
            self.season = "2024"
            self.end_week = "20"
            
    mocker.patch("src.fetcher.yahoofantasy.League", MockFallbackLeague)
    
    fetcher = YahooFantasyFetcher()
    data = fetcher.fetch_league_metadata("12345")
    
    assert data["name"] == "Fallback League"
    assert data["start_date"] == "2024-01-01"

def test_parse_stats_various_formats(mocker):
    fetcher = YahooFantasyFetcher()
    
    class ComplexStat:
        def __init__(self):
            # _parse_stats explicitly checks for outcome_totals
            self.outcome_totals = type('Outcome', (), {'wins': '5', 'losses': '2'})()
            self.points_for = '100'
    
    class ComplexTeam:
        def __init__(self):
            self.team_standings = ComplexStat()
            
    team = ComplexTeam()
    stats = fetcher._parse_stats(team)
    
    assert stats["outcome_totals_wins"] == '5'
    assert stats["outcome_totals_losses"] == '2'
    assert stats["points_for"] == '100'

def test_fetch_batch_rosters_error(mocker):
    mock_ctx = mocker.patch("src.fetcher.yahoofantasy.Context").return_value
    mock_ctx.make_request.side_effect = Exception("API Error")
    
    fetcher = YahooFantasyFetcher()
    data = fetcher.fetch_batch_rosters("12345", "2023-11-01")
    
    assert data == {}

def test_fetch_league_scoreboard_error(mocker):
    mock_ctx = mocker.patch("src.fetcher.yahoofantasy.Context").return_value
    mock_ctx.make_request.side_effect = Exception("API Error")
    
    fetcher = YahooFantasyFetcher()
    data = fetcher.fetch_league_scoreboard("12345", 1)
    
    assert data == {}

def test_parse_teams_from_content_with_game_counts(mocker):
    fetcher = YahooFantasyFetcher()
    data = {
        "fantasy_content": {
            "league": {
                "teams": {
                    "team": [
                        {
                            "team_id": "1", 
                            "name": "Team A",
                            "team_remaining_games": {
                                "total": {
                                    "completed_games": "2",
                                    "live_games": {"$": "1"},
                                    "remaining_games": "3"
                                }
                            }
                        }
                    ]
                }
            }
        }
    }
    
    mocker.patch("yahoofantasy.resources.team.Team")
    mocker.patch("yahoofantasy.api.parse.from_response_object")
    
    parsed = fetcher._parse_teams_from_content(data)
    team = parsed["team_stats"][0]
    
    assert team["stats"]["GP_PLAYED"] == 3
    assert team["stats"]["GP_TOTAL"] == 6

def test_parse_teams_from_content_error_handling(mocker):
    fetcher = YahooFantasyFetcher()
    # Invalid data format
    data = {"fantasy_content": {}}
    
    parsed = fetcher._parse_teams_from_content(data)
    assert parsed == {"team_stats": []}

def test_parse_scoreboard_success(mocker):
    fetcher = YahooFantasyFetcher()
    data = {
        "fantasy_content": {
            "league": {
                "scoreboard": {
                    "matchups": {
                        "matchup": [
                            {
                                "teams": {
                                    "team": [
                                        {"team_id": "1", "name": "Team A"}
                                    ]
                                }
                            }
                        ]
                    }
                }
            }
        }
    }
    
    mocker.patch("yahoofantasy.resources.team.Team")
    def mock_from_resp(t, d):
        t.team_id = d["team_id"]
        t.name = d["name"]
    mocker.patch("yahoofantasy.api.parse.from_response_object", side_effect=mock_from_resp)
    mocker.patch.object(YahooFantasyFetcher, "_parse_stats", return_value={"PTS": "100"})
    
    parsed = fetcher._parse_scoreboard(data)
    assert len(parsed["team_stats"]) == 1
    assert parsed["team_stats"][0]["name"] == "Team A"

def test_parse_scoreboard_error(mocker):
    fetcher = YahooFantasyFetcher()
    # Invalid data format
    data = {"fantasy_content": {}}
    
    parsed = fetcher._parse_scoreboard(data)
    assert parsed == {"team_stats": []}
