import pytest
from datetime import datetime
import pytz
from src.live_api_fetcher import EspnLivePlayerFetcher


def test_espn_fetcher_search_player_and_compute_stats(mocker):
    mock_get = mocker.patch("src.live_api_fetcher.requests.get")
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "items": [
            {
                "id": "1966",
                "uid": "s:40~l:46~a:1966",
                "displayName": "LeBron James",
                "league": "nba",
                "sport": "basketball",
                "jersey": "23",
                "position": {"abbreviation": "SF"},
                "teamRelationships": [
                    {
                        "core": {
                            "id": "13",
                            "abbreviation": "LAL",
                            "displayName": "Los Angeles Lakers",
                        }
                    }
                ],
            }
        ]
    }

    fetcher = EspnLivePlayerFetcher()
    player = fetcher.search_player("LeBron James")

    assert player is not None
    assert player["athlete_id"] == "1966"
    assert player["english_name"] == "LeBron James"
    assert player["team_id"] == "13"
    assert player["team_abbr"] == "LAL"
    assert player["team_name"] == "Los Angeles Lakers"
    assert player["jersey_number"] == "23"
    assert player["position"] == "SF"

    raw_boxscore = {
        "MIN": "35",
        "FG": "12-19",
        "3PT": "3-7",
        "FT": "5-6",
        "OREB": "2",
        "DREB": "8",
        "REB": "10",
        "AST": "11",
        "STL": "2",
        "BLK": "1",
        "TO": "2",
        "PTS": "32",
    }
    stats = fetcher.compute_fantasy_stats_from_raw(raw_boxscore)
    assert stats["MIN"] == "35"
    assert stats["FGM/A"] == "12/19"
    assert stats["FG%"] == "63.2%"
    assert stats["FTM/A"] == "5/6"
    assert stats["FT%"] == "83.3%"
    assert stats["3PT"] == "3"
    assert stats["PTS"] == "32"
    assert stats["REB"] == "10"
    assert stats["AST"] == "11"
    assert stats["ST"] == "2"
    assert stats["BLK"] == "1"
    assert stats["TO"] == "2"
    assert stats["DD"] == "1"
    assert stats["TD"] == "1"
    assert stats["A/T"] == "5.50"


def test_espn_fetcher_live_and_final_game_boxscore(mocker):
    pac_tz = pytz.timezone("US/Pacific")
    now_pac = pac_tz.localize(datetime(2026, 11, 24, 20, 30, 0))

    scoreboard_live = {
        "events": [
            {
                "id": "401704801",
                "date": "2026-11-25T03:00Z",
                "competitions": [
                    {
                        "status": {
                            "period": 3,
                            "displayClock": "04:12",
                            "type": {
                                "state": "in",
                                "shortDetail": "4:12 - 3rd",
                            },
                        },
                        "competitors": [
                            {"team": {"id": "13", "abbreviation": "LAL"}, "score": "88"},
                            {"team": {"id": "9", "abbreviation": "GSW"}, "score": "82"},
                        ],
                    }
                ],
            }
        ]
    }
    summary_live = {
        "boxscore": {
            "players": [
                {
                    "team": {"id": "13", "abbreviation": "LAL"},
                    "statistics": [
                        {
                            "labels": [
                                "MIN", "FG", "3PT", "FT", "OREB", "DREB",
                                "REB", "AST", "STL", "BLK", "TO", "PF", "+/-", "PTS",
                            ],
                            "athletes": [
                                {
                                    "athlete": {
                                        "id": "1966",
                                        "displayName": "LeBron James",
                                        "jersey": "23",
                                        "position": {"abbreviation": "SF"},
                                    },
                                    "didNotPlay": False,
                                    "stats": [
                                        "28", "9-15", "2-5", "4-5", "1", "6",
                                        "7", "8", "1", "1", "2", "1", "+6", "24",
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ]
        }
    }

    def side_effect_live(url, params=None, timeout=10):
        resp = mocker.MagicMock()
        resp.status_code = 200
        if "scoreboard" in url:
            resp.json.return_value = scoreboard_live
        else:
            resp.json.return_value = summary_live
        return resp

    mocker.patch("src.live_api_fetcher.requests.get", side_effect=side_effect_live)

    fetcher = EspnLivePlayerFetcher()
    player_info = {
        "athlete_id": "1966",
        "english_name": "LeBron James",
        "team_id": "13",
        "team_abbr": "LAL",
        "jersey_number": "23",
        "position": "SF",
    }
    game_data = fetcher.fetch_player_live_or_latest_game(player_info, now_pacific=now_pac)

    assert game_data is not None
    assert game_data["game_state"] == "in"
    assert game_data["status_label"] == "🔴 LIVE • Q3 04:12"
    assert game_data["score_text"] == "LAL 88 : 82 GSW"
    assert game_data["game_date"] == "2026-11-24"
    assert game_data["minutes"] == "28"
    assert game_data["notice_banner"] is None
    assert game_data["stats"]["FGM/A"] == "9/15"
    assert game_data["stats"]["FG%"] == "60.0%"
    assert game_data["stats"]["PTS"] == "24"
    assert game_data["stats"]["DD"] == "0"
    assert game_data["stats"]["A/T"] == "4.00"

    # Now verify FINAL game state ('post')
    scoreboard_final = {
        "events": [
            {
                "id": "401704801",
                "competitions": [
                    {
                        "status": {
                            "period": 4,
                            "displayClock": "0.0",
                            "type": {
                                "state": "post",
                                "shortDetail": "Final",
                            },
                        },
                        "competitors": [
                            {"team": {"id": "13", "abbreviation": "LAL"}, "score": "115"},
                            {"team": {"id": "9", "abbreviation": "GSW"}, "score": "108"},
                        ],
                    }
                ],
            }
        ]
    }
    summary_final = {
        "boxscore": {
            "players": [
                {
                    "team": {"id": "13", "abbreviation": "LAL"},
                    "statistics": [
                        {
                            "labels": [
                                "MIN", "FG", "3PT", "FT", "OREB", "DREB",
                                "REB", "AST", "STL", "BLK", "TO", "PF", "+/-", "PTS",
                            ],
                            "athletes": [
                                {
                                    "athlete": {"id": "1966", "displayName": "LeBron James"},
                                    "didNotPlay": False,
                                    "stats": [
                                        "36", "14-24", "4-8", "3-4", "2", "8",
                                        "10", "12", "2", "1", "3", "2", "+7", "35",
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ]
        }
    }

    def side_effect_final(url, params=None, timeout=10):
        resp = mocker.MagicMock()
        resp.status_code = 200
        if "scoreboard" in url:
            resp.json.return_value = scoreboard_final
        else:
            resp.json.return_value = summary_final
        return resp

    mocker.patch("src.live_api_fetcher.requests.get", side_effect=side_effect_final)
    final_data = fetcher.fetch_player_live_or_latest_game(player_info, now_pacific=now_pac)

    assert final_data is not None
    assert final_data["game_state"] == "post"
    assert final_data["status_label"] == "🏁 FINAL"
    assert final_data["score_text"] == "LAL 115 : 108 GSW"
    assert final_data["minutes"] == "36"
    assert final_data["stats"]["PTS"] == "35"
    assert final_data["stats"]["REB"] == "10"
    assert final_data["stats"]["AST"] == "12"
    assert final_data["stats"]["DD"] == "1"
    assert final_data["stats"]["TD"] == "1"


def test_live_player_flex_renderer_default_and_custom_categories():
    from src.visualizer.live_player_flex_renderer import LivePlayerFlexRenderer

    renderer = LivePlayerFlexRenderer()
    player_info = {
        "athlete_id": "1966",
        "english_name": "LeBron James",
        "chinese_name": "勒布朗·詹姆斯",
        "team_abbr": "LAL",
        "jersey_number": "23",
        "position": "SF",
    }
    stats = {
        "MIN": "35",
        "FGM/A": "12/19",
        "FG%": "63.2%",
        "FTM/A": "5/6",
        "FT%": "83.3%",
        "3PT": "3",
        "PTS": "32",
        "REB": "10",
        "AST": "11",
        "ST": "2",
        "BLK": "1",
        "TO": "2",
        "DD": "1",
        "A/T": "5.50",
    }
    game_data = {
        "game_date": "2026-11-24",
        "game_state": "in",
        "status_label": "🔴 LIVE • Q3 04:12",
        "score_text": "LAL 88 : 82 GSW",
        "minutes": "35",
        "stats": stats,
        "notice_banner": None,
    }

    # 1. Default 9-cat order (with FGM/A and FTM/A -> 11 rows)
    bubble = renderer.render_player_card(player_info, game_data)
    assert bubble["type"] == "bubble"
    body_contents = bubble["body"]["contents"]

    # Header: English name & subtitle
    header_box = body_contents[0]
    assert header_box["contents"][0]["text"] == "LeBron James"
    assert header_box["contents"][1]["text"] == "勒布朗·詹姆斯 ｜ LAL #23 • SF"

    # Status box (no notice_banner, so index 1 is status box)
    status_box = body_contents[1]
    assert status_box["backgroundColor"] == "#F8F9F9"
    assert status_box["contents"][0]["text"] == "🔴 LIVE • Q3 04:12"
    assert status_box["contents"][0]["color"] == "#C0392B"
    assert status_box["contents"][1]["text"] == "LAL 88 : 82 GSW"

    # Stats section after separator (index 3)
    stats_section = body_contents[3]
    date_min_row = stats_section["contents"][0]
    assert date_min_row["contents"][0]["text"] == "2026-11-24"
    assert date_min_row["contents"][1]["text"] == "MIN 35"

    stat_rows_box = stats_section["contents"][1]["contents"]
    labels = [r["contents"][0]["text"] for r in stat_rows_box]
    values = [r["contents"][1]["text"] for r in stat_rows_box]
    assert labels == [
        "FGM/A", "FG%", "FTM/A", "FT%", "3PT",
        "PTS", "REB", "AST", "ST", "BLK", "TO",
    ]
    assert values == [
        "12/19", "63.2%", "5/6", "83.3%", "3",
        "32", "10", "11", "2", "1", "2",
    ]

    # 2. Custom league stat_categories (including DD and AST/TO) + FINAL + notice_banner
    custom_cats = [
        {"display_name": "FG%"},
        {"display_name": "FT%"},
        {"display_name": "3PTM"},
        {"display_name": "PTS"},
        {"display_name": "REB"},
        {"display_name": "AST"},
        {"display_name": "STL"},
        {"display_name": "BLK"},
        {"display_name": "TO"},
        {"display_name": "DD"},
        {"display_name": "AST/TO"},
    ]
    final_game_data = {
        **game_data,
        "game_state": "post",
        "status_label": "🏁 FINAL",
        "notice_banner": "⚠️ 今日未出賽 (DNP - Rest) • 以下為最近出賽",
    }
    custom_bubble = renderer.render_player_card(player_info, final_game_data, stat_categories=custom_cats)
    c_body = custom_bubble["body"]["contents"]

    # Index 1 is notice_banner
    banner_box = c_body[1]
    assert banner_box["backgroundColor"] == "#FEF9E7"
    assert banner_box["contents"][0]["text"] == "⚠️ 今日未出賽 (DNP - Rest) • 以下為最近出賽"

    # Index 2 is status_box with FINAL color #2C3E50
    c_status_box = c_body[2]
    assert c_status_box["contents"][0]["text"] == "🏁 FINAL"
    assert c_status_box["contents"][0]["color"] == "#2C3E50"

    c_stat_rows = c_body[4]["contents"][1]["contents"]
    c_labels = [r["contents"][0]["text"] for r in c_stat_rows]
    c_values = [r["contents"][1]["text"] for r in c_stat_rows]
    assert c_labels == [
        "FGM/A", "FG%", "FTM/A", "FT%", "3PT",
        "PTS", "REB", "AST", "ST", "BLK", "TO", "DD", "A/T",
    ]
    assert c_values[-2:] == ["1", "5.50"]


def test_live_player_handler_execute_nba_live_and_mlb_rejection(mocker, tmp_path):
    from unittest.mock import MagicMock
    from linebot.v3.webhooks import MessageEvent
    from linebot.v3.messaging import Configuration
    from src.handlers.live_player_handler import LivePlayerHandler

    mocker.patch("src.utils.path_utils.DATA_DIR", str(tmp_path))
    mocker.patch(
        "src.utils.live_player_cache.DEFAULT_LIVE_CACHE_PATH",
        str(tmp_path / "live_player_mapping_cache.json"),
    )

    event = MagicMock(spec=MessageEvent)
    event.message = MagicMock()
    event.reply_token = "test_token"
    config = MagicMock(spec=Configuration)

    handler = LivePlayerHandler()
    assert handler.can_handle("#球員 LeBron James") is True
    assert handler.can_handle("#球員") is False
    assert handler.can_handle("#玩家 LeBron") is False

    # 1. MLB League rejection
    mocker.patch("src.handlers.live_player_handler.load_config", return_value={"LEAGUE_ID": "mlb.l.999"})
    mocker.patch("src.handlers.live_player_handler.load_league_metadata", return_value={"sport": "mlb"})
    mock_reply_text = mocker.patch.object(handler, "reply_text")
    mock_reply_flex = mocker.patch.object(handler, "reply_flex")

    event.message.text = "#球員 Shohei Ohtani"
    handler.execute(event, config)
    mock_reply_text.assert_called_once_with(
        event, config, "⚠️ 球員即時數據查詢目前僅支援 NBA 聯賽。"
    )
    mock_reply_flex.assert_not_called()

    # 2. NBA League live player query end-to-end
    mock_reply_text.reset_mock()
    mocker.patch("src.handlers.live_player_handler.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch(
        "src.handlers.live_player_handler.load_league_metadata",
        return_value={
            "sport": "nba",
            "stat_categories": [
                {"display_name": "FG%"},
                {"display_name": "FT%"},
                {"display_name": "3PTM"},
                {"display_name": "PTS"},
                {"display_name": "REB"},
                {"display_name": "AST"},
                {"display_name": "STL"},
                {"display_name": "BLK"},
                {"display_name": "TO"},
            ],
        },
    )
    mocker.patch.object(
        handler.fetcher,
        "search_player",
        return_value={
            "athlete_id": "1966",
            "english_name": "LeBron James",
            "chinese_name": "勒布朗·詹姆斯",
            "team_id": "13",
            "team_abbr": "LAL",
            "team_name": "Los Angeles Lakers",
            "jersey_number": "23",
            "position": "SF",
        },
    )
    mocker.patch.object(
        handler.fetcher,
        "fetch_player_live_or_latest_game",
        return_value={
            "event_id": "401704801",
            "game_date": "2026-11-24",
            "game_state": "in",
            "status_label": "🔴 LIVE • Q3 04:12",
            "score_text": "LAL 88 : 82 GSW",
            "minutes": "28",
            "stats": {
                "MIN": "28",
                "FGM/A": "9/15",
                "FG%": "60.0%",
                "FTM/A": "4/5",
                "FT%": "80.0%",
                "3PT": "2",
                "PTS": "24",
                "REB": "7",
                "AST": "8",
                "ST": "1",
                "BLK": "1",
                "TO": "2",
            },
            "notice_banner": None,
        },
    )

    event.message.text = "#球員 LeBron James"
    handler.execute(event, config)

    mock_reply_flex.assert_called_once()
    call_args = mock_reply_flex.call_args[0]
    assert "LeBron James" in call_args[2]
    flex_bubble = call_args[3]
    assert flex_bubble["type"] == "bubble"
    assert flex_bubble["body"]["contents"][0]["contents"][0]["text"] == "LeBron James"
    assert flex_bubble["body"]["contents"][1]["contents"][0]["text"] == "🔴 LIVE • Q3 04:12"


def test_live_player_handler_not_found_and_zero_attempt_stats(mocker, tmp_path):
    from unittest.mock import MagicMock
    from linebot.v3.webhooks import MessageEvent
    from linebot.v3.messaging import Configuration
    from src.handlers.live_player_handler import LivePlayerHandler

    mocker.patch("src.utils.path_utils.DATA_DIR", str(tmp_path))
    mocker.patch(
        "src.utils.live_player_cache.DEFAULT_LIVE_CACHE_PATH",
        str(tmp_path / "live_player_mapping_cache.json"),
    )
    mocker.patch("src.handlers.live_player_handler.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch("src.handlers.live_player_handler.load_league_metadata", return_value={"sport": "nba"})

    event = MagicMock(spec=MessageEvent)
    event.message = MagicMock()
    event.reply_token = "test_token"
    config = MagicMock(spec=Configuration)

    handler = LivePlayerHandler()
    mock_reply_text = mocker.patch.object(handler, "reply_text")

    # 1. Player not found in ESPN search
    mocker.patch.object(handler.fetcher, "search_player", return_value=None)
    event.message.text = "#球員 UnknownGuyXYZ"
    handler.execute(event, config)
    mock_reply_text.assert_called_once_with(
        event,
        config,
        "找不到現役 NBA 球員「UnknownGuyXYZ」，請嘗試輸入更清晰的名字或別稱。",
    )

    # 2. Zero attempts and zero turnovers calculation
    raw_zero = {
        "MIN": "5",
        "FG": "0-0",
        "3PT": "0-0",
        "FT": "0-0",
        "PTS": "0",
        "REB": "1",
        "AST": "2",
        "STL": "0",
        "BLK": "0",
        "TO": "0",
    }
    computed = handler.fetcher.compute_fantasy_stats_from_raw(raw_zero)
    assert computed["FGM/A"] == "0/0"
    assert computed["FG%"] == "-"
    assert computed["FTM/A"] == "0/0"
    assert computed["FT%"] == "-"
    assert computed["DD"] == "0"
    assert computed["TD"] == "0"
    assert computed["A/T"] == "2.00"




