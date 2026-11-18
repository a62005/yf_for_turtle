import json
from datetime import datetime
import pytz
import pytest
from unittest.mock import MagicMock
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration

from src.handlers.local_matchup_handler import LocalMatchupHandler
from src.handlers.local_user_stats_handler import LocalUserStatsHandler
from src.handlers.misc_handler import MiscHandler
from src.handlers.dispatcher import CommandDispatcher
from src.handlers.stats_handler import StatsHandler


@pytest.fixture
def mock_event():
    event = MagicMock(spec=MessageEvent)
    event.message = MagicMock()
    event.source = MagicMock()
    event.source.user_id = "test_user"
    event.reply_token = "dummy_reply_token"
    return event


@pytest.fixture
def mock_config():
    return MagicMock(spec=Configuration)


def test_local_matchup_handler_can_handle(mocker, tmp_path):
    mocker.patch("src.utils.path_utils.DATA_DIR", str(tmp_path))
    mocker.patch("src.handlers.local_matchup_handler.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch.object(LocalMatchupHandler, "_load_team_mapping", return_value={"1": "韋哥", "2": "Jerry"})

    handler = LocalMatchupHandler()
    assert handler.can_handle("#對戰") is True
    assert handler.can_handle("#對戰 ") is True
    assert handler.can_handle("#對戰 韋哥") is True
    assert handler.can_handle("#對戰 Jerry") is True
    assert handler.can_handle("#對戰 詹姆斯") is False
    assert handler.can_handle("#戰績") is False


def test_local_matchup_no_nickname_shows_player_list(mocker, mock_event, mock_config):
    handler = LocalMatchupHandler()
    mock_event.message.text = "#對戰"
    mock_reply_list = mocker.patch.object(handler, "reply_player_list")

    handler.execute(mock_event, mock_config)
    mock_reply_list.assert_called_once_with(mock_event, mock_config, is_matchup=True)


def test_local_matchup_execute_with_explicit_matchups(mocker, tmp_path, mock_event, mock_config):
    mocker.patch("src.utils.path_utils.DATA_DIR", str(tmp_path))
    mocker.patch("src.handlers.local_matchup_handler.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch("src.handlers.local_matchup_handler.load_league_metadata", return_value=None)
    mocker.patch.object(
        LocalMatchupHandler,
        "_load_team_mapping",
        return_value={"1": "韋哥", "2": "Jerry", "3": "陳威", "4": "阿明"},
    )
    tw_tz = pytz.timezone("Asia/Taipei")
    mocker.patch(
        "src.handlers.local_matchup_handler._get_now_tw",
        return_value=tw_tz.localize(datetime(2026, 4, 5, 15, 0, 0)),
    )

    weekly_dir = tmp_path / "league" / "nba" / "123" / "weekly"
    weekly_dir.mkdir(parents=True, exist_ok=True)
    weekly_payload = {
        "league_id": "nba.l.123",
        "date": "2026-04-04",
        "week": 23,
        "matchups": [
            {"team1_id": "1", "team2_id": "4"},
            {"team1_id": "2", "team2_id": "3"},
        ],
        "team_stats": [
            {
                "team_id": "1",
                "name": "韋哥",
                "official_name": "Vigo Official",
                "stats": {
                    "FGM/A": "180/350",
                    "FG%": 0.514,
                    "FTM/A": "0/0",
                    "FT%": 0.0,
                    "3PT": 35,
                    "PTS": 450,
                    "REB": 110,
                    "AST": 95,
                    "ST": 25,
                    "BLK": 12,
                    "TO": 32,
                },
            },
            {
                "team_id": "2",
                "name": "Jerry",
                "official_name": "Jerry Official",
                "stats": {"PTS": 100},
            },
            {
                "team_id": "3",
                "name": "陳威",
                "official_name": "Chen Official",
                "stats": {"PTS": 120},
            },
            {
                "team_id": "4",
                "name": "阿明",
                "official_name": "Ming Official",
                "stats": {
                    "FGM/A": "165/340",
                    "FG%": 0.485,
                    "FTM/A": "15/20",
                    "FT%": 0.750,
                    "3PT": 42,
                    "PTS": 410,
                    "REB": 125,
                    "AST": 80,
                    "ST": 20,
                    "BLK": 18,
                    "TO": 38,
                },
            },
        ],
    }
    (weekly_dir / "date_2026-04-04_weekly.json").write_text(
        json.dumps(weekly_payload, ensure_ascii=False), encoding="utf-8"
    )

    handler = LocalMatchupHandler()
    mock_reply_flex = mocker.patch.object(handler, "reply_flex")
    mock_event.message.text = "#對戰 韋哥"

    handler.execute(mock_event, mock_config)

    mock_reply_flex.assert_called_once()
    call_args = mock_reply_flex.call_args[0]
    assert call_args[2] == "WEEK 23 MATCHUP - 韋哥 vs 阿明"
    bubble = call_args[3]
    assert bubble["type"] == "bubble"
    body = bubble["body"]["contents"]
    assert body[0]["text"] == "WEEK 23 MATCHUP"
    assert body[1]["contents"][0]["text"] == "韋哥"
    assert body[1]["contents"][2]["text"] == "阿明"
    assert body[2]["contents"][0]["text"] == "Vigo Official"
    assert body[2]["contents"][2]["text"] == "Ming Official"
    assert body[3]["contents"][0]["text"] == "5"
    assert body[3]["contents"][2]["text"] == "4"


def test_local_matchup_fallback_to_latest_file_and_adjacent_pairs(mocker, tmp_path, mock_event, mock_config):
    mocker.patch("src.utils.path_utils.DATA_DIR", str(tmp_path))
    mocker.patch("src.handlers.local_matchup_handler.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch(
        "src.handlers.local_matchup_handler.load_league_metadata",
        return_value={
            "start_date": "2025-10-20",
            "end_date": "2026-04-12",
            "end_week": 24,
            "stat_categories": [
                {"stat_id": "9004003", "display_name": "FGM/A", "sort_order": 1},
                {"stat_id": "5", "display_name": "FG%", "sort_order": 1},
                {"stat_id": "9007006", "display_name": "FTM/A", "sort_order": 1},
                {"stat_id": "8", "display_name": "FT%", "sort_order": 1},
                {"stat_id": "10", "display_name": "3PTM", "sort_order": 1},
                {"stat_id": "12", "display_name": "PTS", "sort_order": 1},
                {"stat_id": "15", "display_name": "REB", "sort_order": 1},
                {"stat_id": "16", "display_name": "AST", "sort_order": 1},
                {"stat_id": "17", "display_name": "ST", "sort_order": 1},
                {"stat_id": "18", "display_name": "BLK", "sort_order": 1},
                {"stat_id": "19", "display_name": "TO", "sort_order": 0},
            ],
        },
    )
    mocker.patch.object(
        LocalMatchupHandler,
        "_load_team_mapping",
        return_value={"1": "韋哥", "2": "Jerry"},
    )
    # 模擬今天時間是 2026-04-06，但本地只有 2026-04-04 的舊格式 weekly 檔案（無 matchups 欄位）
    tw_tz = pytz.timezone("Asia/Taipei")
    mocker.patch(
        "src.handlers.local_matchup_handler._get_now_tw",
        return_value=tw_tz.localize(datetime(2026, 4, 6, 15, 0, 0)),
    )

    weekly_dir = tmp_path / "league" / "nba" / "123" / "weekly"
    weekly_dir.mkdir(parents=True, exist_ok=True)
    weekly_payload = {
        "league_id": "nba.l.123",
        "date": "2026-04-04",
        "team_stats": [
            {
                "team_id": "1",
                "name": "韋哥",
                "stats": {
                    "FGM/A": "180/350",
                    "FG%": 0.514,
                    "FTM/A": "20/25",
                    "FT%": 0.800,
                    "3PT": 35,
                    "PTS": 450,
                    "REB": 110,
                    "AST": 95,
                    "ST": 25,
                    "BLK": 12,
                    "TO": 32,
                },
            },
            {
                "team_id": "2",
                "name": "Jerry",
                "stats": {
                    "FGM/A": "165/340",
                    "FG%": 0.485,
                    "FTM/A": "15/20",
                    "FT%": 0.750,
                    "3PT": 42,
                    "PTS": 410,
                    "REB": 125,
                    "AST": 80,
                    "ST": 20,
                    "BLK": 18,
                    "TO": 38,
                },
            },
        ],
    }
    (weekly_dir / "date_2026-04-04_weekly.json").write_text(
        json.dumps(weekly_payload, ensure_ascii=False), encoding="utf-8"
    )

    handler = LocalMatchupHandler()
    mock_reply_flex = mocker.patch.object(handler, "reply_flex")
    mock_event.message.text = "#對戰 Jerry"

    handler.execute(mock_event, mock_config)

    mock_reply_flex.assert_called_once()
    call_args = mock_reply_flex.call_args[0]
    assert "Jerry vs 韋哥" in call_args[2]
    bubble = call_args[3]
    body = bubble["body"]["contents"]
    # Jerry 贏 3PTM, REB, BLK (3 項)，韋哥贏 FG%, FT%, PTS, AST, ST, TO (6 項)，FGM/A 與 FTM/A 為輔助行不計入勝負
    assert body[3]["contents"][0]["text"] == "3"
    assert body[3]["contents"][2]["text"] == "6"


def test_help_menu_displays_local_matchup_and_local_user_stats(mocker, mock_event, mock_config):
    mocker.patch("src.handlers.misc_handler.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch("src.handlers.misc_handler.security_manager.is_whitelisted", return_value=False)

    dispatcher = CommandDispatcher()
    dispatcher.register(StatsHandler())
    dispatcher.register(LocalUserStatsHandler())
    dispatcher.register(LocalMatchupHandler())
    misc_handler = MiscHandler()
    dispatcher.register(misc_handler)

    mock_reply_flex = mocker.patch.object(misc_handler, "reply_flex")
    mock_event.message.text = "#幫助"

    misc_handler.execute(mock_event, mock_config)

    mock_reply_flex.assert_called_once()
    flex_dict = mock_reply_flex.call_args[0][3]
    flex_str = json.dumps(flex_dict, ensure_ascii=False)
    assert "即時對決" in flex_str
    assert "#對戰" in flex_str
    assert "玩家數據" in flex_str
    assert "#玩家" in flex_str
