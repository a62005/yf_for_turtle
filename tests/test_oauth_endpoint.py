import json
import pickle
import pytest
from unittest.mock import MagicMock, patch

@pytest.fixture
def mock_app():
    from bot import app
    app.config["TESTING"] = True
    return app.test_client()

def test_oauth_callback_success(mock_app):
    # 模擬 chat_league_mapping.json 的讀寫
    mapping_data = {"C_test_group": "77777"}
    
    # Mock Token 交換回傳值
    mock_token_payload = {
        "access_token": "mock_access_token_123",
        "refresh_token": "mock_refresh_token_456",
        "expires_in": 3600,
        "token_type": "bearer"
    }
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_token_payload
    
    # 記錄所有 pickle.dump 呼叫的資料
    pickled_data = {}
    original_pickle_dump = pickle.dump
    
    def mock_pickle_dump(data, fp, *args, **kwargs):
        try:
            pickled_data[fp.name] = data
        except AttributeError:
            pass
    
    with patch("bot.load_config", return_value={"YAHOO_CLIENT_ID": "client", "YAHOO_CLIENT_SECRET": "secret", "SERVER_URL": "http://127.0.0.1"}), \
         patch("bot.requests.post", return_value=mock_response) as mock_post, \
         patch("bot.os.path.exists", return_value=True), \
         patch("bot.json.load", return_value=mapping_data), \
         patch("bot.os.makedirs"), \
         patch("bot.pickle.load", return_value={}), \
         patch("bot.pickle.dump", side_effect=mock_pickle_dump), \
         patch("builtins.open", MagicMock()), \
         patch("src.fetcher.YahooFantasyFetcher") as mock_fetcher_cls, \
         patch("src.utils.season_utils.sync_season_metadata") as mock_sync_season, \
         patch("yahoofantasy.League") as mock_league_cls, \
         patch("linebot.v3.messaging.MessagingApi") as mock_api_cls:
         
        # Mock fetcher instance and its methods
        mock_fetcher = MagicMock()
        mock_fetcher._normalize_league_id.return_value = "77777"
        mock_fetcher_cls.return_value = mock_fetcher
        
        # Mock league.teams() return values
        mock_team = MagicMock()
        mock_team.team_id = "1"
        mock_team.name = "Test Team"
        mock_league = MagicMock()
        mock_league.teams.return_value = [mock_team]
        mock_league_cls.return_value = mock_league

        # 發送 GET 請求
        res = mock_app.get("/oauth/callback?code=code_123&state=C_test_group")
        
        # 驗證響應
        assert res.status_code == 200
        assert "授權成功" in res.get_data(as_text=True)
        
        # 驗證 POST 請求參數
        mock_post.assert_called_once()
        post_kwargs = mock_post.call_args[1]
        assert post_kwargs["data"]["code"] == "code_123"
        
        # 驗證有呼叫 pickle.dump（代表 .yahoofantasy 被寫入）
        from bot import pickle as bot_pickle
        bot_pickle.dump.assert_called()
        
        # 驗證有呼叫初始化與同步
        mock_fetcher_cls.assert_called_once_with(
            client_id="client",
            client_secret="secret",
            league_id="77777"
        )
        mock_sync_season.assert_called_once_with(mock_fetcher, "77777")
        
        # 驗證是否對群組調用 Push Message 推播成功訊息
        mock_api_cls.assert_called_once()
