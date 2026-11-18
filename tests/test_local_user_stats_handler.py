import json
from datetime import datetime
import pytz
import pytest
from unittest.mock import MagicMock
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration

from src.handlers.local_user_stats_handler import LocalUserStatsHandler


@pytest.fixture
def mock_event():
    event = MagicMock(spec=MessageEvent)
    event.message = MagicMock()
    event.reply_token = "dummy_reply_token"
    return event


@pytest.fixture
def mock_config():
    return MagicMock(spec=Configuration)


def test_local_user_stats_can_handle(mocker, tmp_path):
    mocker.patch("src.utils.path_utils.DATA_DIR", str(tmp_path))
    mocker.patch("src.handlers.local_user_stats_handler.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch.object(LocalUserStatsHandler, "_load_team_mapping", return_value={"1": "韋哥", "2": "Jerry"})

    handler = LocalUserStatsHandler()
    assert handler.can_handle("#玩家") is True
    assert handler.can_handle("#玩家 ") is True
    assert handler.can_handle("#玩家 韋哥") is True
    assert handler.can_handle("#玩家 Jerry") is True
    assert handler.can_handle("#玩家 Jerry 20260404") is False
    assert handler.can_handle("#玩家 詹姆斯") is False


def test_local_user_stats_no_nickname_shows_player_list(mocker, mock_event, mock_config):
    handler = LocalUserStatsHandler()
    mock_event.message.text = "#玩家"
    mock_reply_list = mocker.patch.object(handler, "reply_player_list")

    handler.execute(mock_event, mock_config)
    mock_reply_list.assert_called_once_with(mock_event, mock_config, is_matchup=False)


def test_local_user_stats_default_date_and_fallback_to_latest(mocker, tmp_path, mock_event, mock_config):
    mocker.patch("src.utils.path_utils.DATA_DIR", str(tmp_path))
    mocker.patch("src.handlers.local_user_stats_handler.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch(
        "src.handlers.local_user_stats_handler.load_league_metadata",
        return_value={"start_date": "2025-10-20", "end_date": "2026-04-15"},
    )
    mocker.patch.object(LocalUserStatsHandler, "_load_team_mapping", return_value={"1": "韋哥", "2": "Jerry"})

    # 模擬台灣時間為 2026-04-06 15:00，但本地最新檔案為 2026-04-04
    tw_tz = pytz.timezone("Asia/Taipei")
    mocker.patch(
        "src.handlers.local_user_stats_handler._get_now_tw",
        return_value=tw_tz.localize(datetime(2026, 4, 6, 15, 0, 0)),
    )

    daily_dir = tmp_path / "league" / "nba" / "123" / "daily"
    weekly_dir = tmp_path / "league" / "nba" / "123" / "weekly"
    daily_dir.mkdir(parents=True, exist_ok=True)
    weekly_dir.mkdir(parents=True, exist_ok=True)

    daily_payload = {
        "league_id": "nba.l.123",
        "date": "2026-04-04",
        "week": 23,
        "team_stats": [
            {
                "team_id": "1",
                "name": "韋哥",
                "official_name": "Vigo's Superteam",
                "stats": {
                    "FGM/A": "14/24",
                    "FG%": 0.583,
                    "FTM/A": "3/4",
                    "FT%": 0.750,
                    "3PT": 4,
                    "PTS": 35,
                    "REB": 9,
                    "AST": 12,
                    "ST": 2,
                    "BLK": 1,
                    "TO": 3,
                },
            }
        ],
    }
    weekly_payload = {
        "league_id": "nba.l.123",
        "date": "2026-04-04",
        "week": 23,
        "team_stats": [
            {
                "team_id": "1",
                "name": "韋哥",
                "official_name": "Vigo's Superteam",
                "stats": {
                    "FGM/A": "80/150",
                    "FG%": 0.533,
                    "FTM/A": "20/25",
                    "FT%": 0.800,
                    "3PT": 18,
                    "PTS": 210,
                    "REB": 55,
                    "AST": 62,
                    "ST": 12,
                    "BLK": 8,
                    "TO": 15,
                },
            }
        ],
    }
    (daily_dir / "date_2026-04-04.json").write_text(
        json.dumps(daily_payload, ensure_ascii=False), encoding="utf-8"
    )
    (weekly_dir / "date_2026-04-04_weekly.json").write_text(
        json.dumps(weekly_payload, ensure_ascii=False), encoding="utf-8"
    )

    handler = LocalUserStatsHandler()
    mock_reply_flex = mocker.patch.object(handler, "reply_flex")
    mock_event.message.text = "#玩家 韋哥"

    handler.execute(mock_event, mock_config)

    mock_reply_flex.assert_called_once()
    args = mock_reply_flex.call_args[0]
    assert args[2] == "玩家 韋哥 數據統計"
    bubble = args[3]
    assert bubble["type"] == "bubble"
    body_contents = bubble["body"]["contents"]
    assert body_contents[0]["contents"][0]["text"] == "韋哥"
    assert body_contents[0]["contents"][1]["text"] == "Vigo's Superteam"
    assert body_contents[1]["contents"][0]["text"] == "2026-04-05"
    assert body_contents[3]["contents"][0]["text"] == "W23"


def test_local_user_stats_missing_local_data_replies_not_found(mocker, tmp_path, mock_event, mock_config):
    mocker.patch("src.utils.path_utils.DATA_DIR", str(tmp_path))
    mocker.patch("src.handlers.local_user_stats_handler.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch(
        "src.handlers.local_user_stats_handler.load_league_metadata",
        return_value={"start_date": "2025-10-20", "end_date": "2026-04-15"},
    )
    mocker.patch.object(LocalUserStatsHandler, "_load_team_mapping", return_value={"1": "韋哥"})

    handler = LocalUserStatsHandler()
    mock_reply_text = mocker.patch.object(handler, "reply_text")

    mock_event.message.text = "#玩家 韋哥"
    handler.execute(mock_event, mock_config)
    mock_reply_text.assert_called_once_with(mock_event, mock_config, "查無當天數據")


def test_intent_router_semantic_mention_triggers_local_user_stats_and_matchup(mocker, tmp_path, mock_event, mock_config):
    from src.handlers.dispatcher import CommandDispatcher
    from src.handlers.intent_router import IntentRouter
    from src.handlers.local_matchup_handler import LocalMatchupHandler

    mocker.patch("src.utils.path_utils.DATA_DIR", str(tmp_path))
    mocker.patch("src.handlers.intent_router.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch("src.handlers.local_user_stats_handler.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch("src.handlers.local_matchup_handler.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch("src.handlers.local_user_stats_handler.load_league_metadata", return_value=None)
    mocker.patch("src.handlers.local_matchup_handler.load_league_metadata", return_value=None)
    mocker.patch.object(LocalUserStatsHandler, "_load_team_mapping", return_value={"1": "肥儒", "2": "Jerry"})
    mocker.patch.object(LocalMatchupHandler, "_load_team_mapping", return_value={"1": "肥儒", "2": "Jerry"})

    dispatcher = CommandDispatcher()
    user_handler = LocalUserStatsHandler()
    matchup_handler = LocalMatchupHandler()
    dispatcher.register(user_handler)
    dispatcher.register(matchup_handler)

    router = IntentRouter(dispatcher)
    mock_user_exec = mocker.patch.object(user_handler, "execute")
    mock_matchup_exec = mocker.patch.object(matchup_handler, "execute")

    mock_event.source = MagicMock()
    mock_event.source.type = "group"
    mock_event.source.user_id = "U_test"

    # 1. @BOT 肥儒 -> LLM 解析為 #玩家 肥儒 -> 觸發 LocalUserStatsHandler
    mocker.patch.object(
        router.llm_agent,
        "analyze_intent",
        return_value={"is_command": True, "command_text": "#玩家 肥儒", "reply_text": None},
    )
    mock_event.message.text = "@bot 肥儒"
    router.route(mock_event, mock_config)
    mock_user_exec.assert_called_once()
    assert mock_event.message.text == "#玩家 肥儒"

    # 2. @BOT 肥儒這週打得怎樣 -> LLM 解析為 #對戰 肥儒 -> 觸發 LocalMatchupHandler
    mocker.patch.object(
        router.llm_agent,
        "analyze_intent",
        return_value={"is_command": True, "command_text": "#對戰 肥儒", "reply_text": None},
    )
    mock_event.message.text = "@bot 肥儒這週打得怎樣"
    router.route(mock_event, mock_config)
    mock_matchup_exec.assert_called_once()
    assert mock_event.message.text == "#對戰 肥儒"

