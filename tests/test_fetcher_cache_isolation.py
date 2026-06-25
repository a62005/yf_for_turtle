import os
import json
import pytest
from unittest.mock import MagicMock, patch
from src.fetcher import YahooFantasyFetcher

def test_fetcher_weekly_stats_saves_to_league_dir(tmp_path):
    fetcher = YahooFantasyFetcher(client_id="dummy", client_secret="dummy")
    
    # Mock Context 的 make_request 回傳
    mock_data = {"test_stats": "data"}
    fetcher.ctx.make_request = MagicMock(return_value=mock_data)
    
    # Mock get_league_weekly_dir 指向 tmp_path
    with patch("src.fetcher.get_league_weekly_dir", return_value=str(tmp_path)):
        res = fetcher.fetch_weekly_stats("18457", 5)
        
        assert res == mock_data
        cache_path = tmp_path / "week_5.json"
        assert cache_path.exists()
        
        # 驗證快取命中
        fetcher.ctx.make_request.reset_mock()
        res_cached = fetcher.fetch_weekly_stats("18457", 5)
        assert res_cached == mock_data
        fetcher.ctx.make_request.assert_not_called()
