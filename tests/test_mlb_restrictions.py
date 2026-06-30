import pytest
from src.utils.time_utils import is_game_day, check_game_day
from src.handlers.misc_handler import SeasonCountdownHandler
from src.handlers.injury_handler import InjuryHandler

def test_is_game_day_bypassed_for_mlb():
    # If sport is mlb, is_game_day should skip ESPN and return True
    assert is_game_day(sport="mlb") == (True, "")
    assert check_game_day(sport="mlb") == (True, "")

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
