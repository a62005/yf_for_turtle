import os
import shutil
import pytest
from unittest.mock import MagicMock, patch
from src.handlers.set_prize_handler import SetPrizeHandler
from src.utils.session_manager import get_prize_session, clear_prize_session

def test_set_prize_handler_can_handle():
    handler = SetPrizeHandler()
    assert handler.can_handle("#設置獎金") is True
    assert handler.can_handle("設置獎金") is False

def test_set_prize_handler_execute_no_league_id():
    handler = SetPrizeHandler()
    event = MagicMock()
    event.source.user_id = "user1"
    config = MagicMock()
    
    with patch("src.handlers.set_prize_handler.load_config", return_value={}), \
         patch.object(handler, "reply_text") as mock_reply:
        handler.execute(event, config)
        mock_reply.assert_called_once_with(event, config, "⚠️ 請先執行 #設置 以綁定聯賽 ID。")

def test_set_prize_handler_execute_success():
    handler = SetPrizeHandler()
    event = MagicMock()
    event.source.user_id = "user1"
    config = MagicMock()
    
    with patch("src.handlers.set_prize_handler.load_config", return_value={"LEAGUE_ID": "nba_123"}), \
         patch.object(handler, "reply_text") as mock_reply:
        handler.execute(event, config)
        mock_reply.assert_called_once_with(event, config, "👉 請在 60 秒內直接傳送新的獎金圖片：")
        assert get_prize_session("user1") is not None
        clear_prize_session("user1")

def test_set_prize_handler_handle_image():
    handler = SetPrizeHandler()
    event = MagicMock()
    event.source.user_id = "user1"
    config = MagicMock()
    
    test_dir = "tests/temp_data/league/nba/123/image"
    os.makedirs(test_dir, exist_ok=True)
    with open(os.path.join(test_dir, "bouns.png"), "w") as f:
        f.write("old")
    with open(os.path.join(test_dir, "bonus.png"), "w") as f:
        f.write("old")
        
    try:
        with patch("src.handlers.set_prize_handler.load_config", return_value={"LEAGUE_ID": "nba_123"}), \
             patch("src.utils.path_utils.parse_league_id", return_value=("nba", "123")), \
             patch("src.utils.path_utils.DATA_DIR", "tests/temp_data"), \
             patch.object(handler, "reply_text") as mock_reply:
            
            handler.handle_image(event, config, b"fake_image_bytes")
            
            assert not os.path.exists(os.path.join(test_dir, "bouns.png"))
            assert not os.path.exists(os.path.join(test_dir, "bonus.png"))
            
            # 尋找新產生的時間戳記檔案並驗證內容
            files = [f for f in os.listdir(test_dir) if f.startswith("bonus_") and f.endswith(".jpg")]
            assert len(files) == 1
            new_file_path = os.path.join(test_dir, files[0])
            with open(new_file_path, "rb") as f:
                assert f.read() == b"fake_image_bytes"
                
            mock_reply.assert_called_once_with(event, config, "✅ 成功設定獎金圖片！")
    finally:
        shutil.rmtree("tests/temp_data", ignore_errors=True)
