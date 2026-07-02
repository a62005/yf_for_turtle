import pytest
from src.utils.time_utils import is_game_day, check_game_day
from src.handlers.misc_handler import SeasonCountdownHandler
from src.handlers.injury_handler import InjuryHandler

def test_is_game_day_bypassed_for_mlb(mocker):
    # If sport is mlb, mock ESPN scoreboard to return no active games (allowing stats query)
    mock_get = mocker.patch("requests.get")
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {"events": []}
    mock_get.return_value = mock_response

    assert is_game_day(sport="mlb") == (True, "")
    assert check_game_day(sport="mlb") == (True, "")

def test_is_game_day_blocked_during_mlb_games(mocker):
    # If sport is mlb and there are active games, it should block queries
    mock_get = mocker.patch("requests.get")
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {
        "events": [
            {"status": {"type": {"state": "in"}}}
        ]
    }
    mock_get.return_value = mock_response

    assert is_game_day(sport="mlb") == (False, "目前仍有比賽正在進行")
    assert check_game_day(sport="mlb") == (False, "目前仍有比賽正在進行")

def test_countdown_handler_restricts_mlb(mocker):
    handler = SeasonCountdownHandler()
    mock_event = mocker.MagicMock()
    mock_event.message.text = "#開季"
    mock_reply = mocker.patch.object(handler, "reply_text")
    
    # Under MLB configuration
    handler.execute(mock_event, {"LEAGUE_ID": "mlb.l.12345"})
    mock_reply.assert_called_with(mock_event, mocker.ANY, "⚠️ 此功能目前僅支援 NBA 聯賽。")

def test_injury_handler_restricts_mlb(mocker):
    handler = SeasonCountdownHandler()
    mock_event = mocker.MagicMock()
    mock_event.message.text = "#傷兵"
    mock_reply = mocker.patch.object(handler, "reply_text")
    
    # Under MLB configuration
    handler.execute(mock_event, {"LEAGUE_ID": "mlb.l.12345"})
    mock_reply.assert_called_with(mock_event, mocker.ANY, "⚠️ 此功能目前僅支援 NBA 聯賽。")
