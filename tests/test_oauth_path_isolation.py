import os
import shutil
import pytest
from unittest.mock import MagicMock
from src.fetcher import YahooFantasyFetcher
from src.utils.path_utils import BASE_DIR

def test_fetcher_oauth_path_isolation_and_fallback(tmp_path):
    # 1. 模擬全域憑證存在
    global_dir = os.path.join(BASE_DIR, "credentials")
    os.makedirs(global_dir, exist_ok=True)
    global_cred = os.path.join(global_dir, "oauth2.json")
    
    with open(global_cred, "w", encoding="utf-8") as f:
        f.write('{"test_token": "global"}')
        
    try:
        # 2. 實例化帶有 league_id 的 fetcher
        league_id = "88888"
        from src.utils.path_utils import get_league_dir
        league_cred_dir = get_league_dir(league_id)
        league_cred_file = os.path.join(league_cred_dir, "oauth2.json")
        
        # 移除舊有聯賽憑證以驗證繼承
        if os.path.exists(league_cred_file):
            os.remove(league_cred_file)
            
        fetcher = YahooFantasyFetcher(client_id="id", client_secret="secret", league_id=league_id)
        
        # 驗證 Context persist_key 是否指向聯賽獨立目錄
        expected_dir = f"data/league/nba/{league_id}/"
        assert fetcher.ctx._persist_key == expected_dir
        
        # 驗證聯賽獨立目錄下是否正確繼承複製了全域憑證
        assert os.path.exists(league_cred_file)
        with open(league_cred_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert "global" in content
            
    finally:
        # 清除測試檔案
        if os.path.exists(global_cred):
            os.remove(global_cred)
        from src.utils.path_utils import get_league_dir
        shutil.rmtree(get_league_dir("88888"), ignore_errors=True)
