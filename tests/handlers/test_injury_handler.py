import pytest
from unittest.mock import MagicMock, patch
from src.handlers.injury_handler import InjuryHandler

# 模擬 Yahoo API 物件結構
class MockPlayer:
    def __init__(self, name, status=None, team_abbr="GSW", injury_note=None, display_pos="PG"):
        self.name = type('Name', (), {'full': name})()
        self.status = status
        self.status_full = "Out" if status == "O" else "Game Time Decision"
        self.editorial_team_abbr = team_abbr
        self.injury_note = injury_note
        self.display_position = display_pos

class MockRoster:
    def __init__(self, players):
        self.players = players

class MockTeam:
    def __init__(self, name, team_id, players):
        self.name = name
        self.team_id = team_id
        self.team_key = f"nba.l.12345.t.{team_id}"
        self._players = players
    def roster(self):
        return MockRoster(self._players)

class MockLeague:
    def __init__(self, teams):
        self._teams = teams
    def teams(self):
        return self._teams

def test_injury_handler_can_handle():
    handler = InjuryHandler()
    assert handler.can_handle("#傷兵 韋哥") is True
    assert handler.can_handle("#傷兵") is True
    assert handler.can_handle("#戰績") is False

@patch("src.handlers.injury_handler.load_config", return_value={"LEAGUE_ID": "12345"})
def test_execute_ignored_on_empty_param(mock_config):
    handler = InjuryHandler()
    event = MagicMock()
    event.message.text = "#傷兵"
    
    with patch.object(handler, "_load_team_mapping", return_value={"1": "韋哥"}):
        with patch("src.handlers.injury_handler.YahooFantasyFetcher") as mock_fetcher:
            handler.execute(event, MagicMock())
            mock_fetcher.assert_not_called()

@patch("src.handlers.injury_handler.load_config", return_value={"LEAGUE_ID": "12345"})
def test_execute_ignored_on_unmatched_player(mock_config):
    handler = InjuryHandler()
    event = MagicMock()
    event.message.text = "#傷兵 找不到的玩家"
    
    with patch.object(handler, "_load_team_mapping", return_value={"1": "韋哥"}):
        with patch("src.handlers.injury_handler.YahooFantasyFetcher") as mock_fetcher:
            handler.execute(event, MagicMock())
            mock_fetcher.assert_not_called()

@patch("src.handlers.injury_handler.load_config", return_value={"LEAGUE_ID": "12345"})
def test_execute_success_with_injuries(mock_config):
    handler = InjuryHandler()
    event = MagicMock()
    event.message.text = "#傷兵 韋哥"
    
    players = [
        MockPlayer("Stephen Curry", status="O", team_abbr="GSW", injury_note="Knee"),
        MockPlayer("Draymond Green", status=None, team_abbr="GSW")
    ]
    mock_team = MockTeam("韋哥隊", "1", players)
    
    mock_ctx = MagicMock()
    mock_league = MockLeague([mock_team])
    
    with patch.object(handler, "_load_team_mapping", return_value={"1": "韋哥"}):
        with patch("src.handlers.injury_handler.YahooFantasyFetcher") as mock_fetcher:
            fetcher_inst = mock_fetcher.return_value
            fetcher_inst.ctx = mock_ctx
            fetcher_inst._normalize_league_id.return_value = "nba.l.12345"
            
            with patch("yahoofantasy.League", return_value=mock_league):
                with patch.object(handler, "reply_flex") as mock_reply:
                    handler.execute(event, MagicMock())
                    
                    mock_reply.assert_called_once()
                    args = mock_reply.call_args[0]
                    alt_text = args[2]
                    flex_dict = args[3]
                    
                    assert "韋哥 的傷兵名單" in alt_text
                    
                    # 1. 驗證白底 Header (置於 body 的首個元件)
                    assert "header" not in flex_dict
                    body_contents = flex_dict["body"]["contents"]
                    header_box = body_contents[0]
                    assert header_box["contents"][0]["text"] == "韋哥"
                    assert header_box["contents"][1]["text"] == "韋哥隊"
                    
                    # 2. 驗證球員數據列 (Curry 應該被縮寫為 S. Curry，並與 - Knee 合併)
                    rows_box = body_contents[2]
                    player_row = rows_box["contents"][0]
                    name_text_box = player_row["contents"][0]
                    assert name_text_box["type"] == "text"
                    assert name_text_box["text"] == "S. Curry - Knee"
                    
                    # 3. 驗證狀態標籤的背景顏色 (O 為深紅)
                    status_box = player_row["contents"][1]
                    assert status_box["backgroundColor"] == "#922B21"
                    assert status_box["contents"][0]["text"] == "O"

@patch("src.handlers.injury_handler.load_config", return_value={"LEAGUE_ID": "12345"})
def test_execute_success_all_healthy(mock_config):
    handler = InjuryHandler()
    event = MagicMock()
    event.message.text = "#傷兵 韋哥"
    
    players = [
        MockPlayer("Stephen Curry", status=None, team_abbr="GSW"),
    ]
    mock_team = MockTeam("韋哥隊", "1", players)
    mock_ctx = MagicMock()
    mock_league = MockLeague([mock_team])
    
    with patch.object(handler, "_load_team_mapping", return_value={"1": "韋哥"}):
        with patch("src.handlers.injury_handler.YahooFantasyFetcher") as mock_fetcher:
            fetcher_inst = mock_fetcher.return_value
            fetcher_inst.ctx = mock_ctx
            fetcher_inst._normalize_league_id.return_value = "nba.l.12345"
            
            with patch("yahoofantasy.League", return_value=mock_league):
                with patch.object(handler, "reply_flex") as mock_reply:
                    handler.execute(event, MagicMock())
                    
                    mock_reply.assert_called_once()
                    flex_dict = mock_reply.call_args[0][3]
                    
                    body_contents = flex_dict["body"]["contents"]
                    assert "目前全隊球員皆健康！" in body_contents[2]["contents"][0]["text"]

@patch("src.handlers.injury_handler.load_config", return_value={"LEAGUE_ID": "12345"})
def test_execute_api_failure(mock_config):
    handler = InjuryHandler()
    event = MagicMock()
    event.message.text = "#傷兵 韋哥"
    
    with patch.object(handler, "_load_team_mapping", return_value={"1": "韋哥"}):
        with patch("src.handlers.injury_handler.YahooFantasyFetcher") as mock_fetcher:
            mock_fetcher.side_effect = Exception("Network Error")
            
            with patch.object(handler, "reply_text") as mock_reply_text:
                handler.execute(event, MagicMock())
                
                # 這裡使用任何 MagicMock 作為 configuration 的斷言
                mock_reply_text.assert_called_once()
                args = mock_reply_text.call_args[0]
                assert args[0] == event
                assert args[2] == "獲取傷兵名單失敗，請稍後再試"

@patch("src.handlers.injury_handler.load_config", return_value={"LEAGUE_ID": "12345"})
def test_execute_player_without_name(mock_config):
    handler = InjuryHandler()
    event = MagicMock()
    event.message.text = "#傷兵 韋哥"
    
    class EmptyPlayer:
        def __init__(self, status="O", injury_note="Knee"):
            self.status = status
            self.injury_note = injury_note
            
    players = [EmptyPlayer()]
    mock_team = MockTeam("韋哥隊", "1", players)
    mock_ctx = MagicMock()
    mock_league = MockLeague([mock_team])
    
    with patch.object(handler, "_load_team_mapping", return_value={"1": "韋哥"}):
        with patch("src.handlers.injury_handler.YahooFantasyFetcher") as mock_fetcher:
            fetcher_inst = mock_fetcher.return_value
            fetcher_inst.ctx = mock_ctx
            fetcher_inst._normalize_league_id.return_value = "nba.l.12345"
            
            with patch("yahoofantasy.League", return_value=mock_league):
                with patch.object(handler, "reply_flex") as mock_reply:
                    handler.execute(event, MagicMock())
                    
                    mock_reply.assert_called_once()
                    flex_dict = mock_reply.call_args[0][3]
                    
                    body_contents = flex_dict["body"]["contents"]
                    rows_box = body_contents[2]
                    player_row = rows_box["contents"][0]
                    name_text_box = player_row["contents"][0]
                    assert "U. Player" in name_text_box["text"]

