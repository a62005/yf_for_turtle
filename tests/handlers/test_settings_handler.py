from unittest.mock import MagicMock, patch
from src.handlers.settings_handler import SettingsHandler

def test_settings_handler_can_handle():
    handler = SettingsHandler()
    assert handler.can_handle("#設置") is True
    assert handler.can_handle("設置") is False

def test_settings_handler_execute_offseason():
    handler = SettingsHandler()
    handler.reply_flex = MagicMock()

    event = MagicMock()
    config = MagicMock()

    with patch("src.handlers.settings_handler.load_config", return_value={"LEAGUE_ID": "12345"}), \
         patch("src.utils.security.security_manager.is_league_manager", return_value=True), \
         patch("src.utils.cache_utils.load_league_metadata", return_value={"end_date": "2026-04-12"}), \
         patch("src.utils.time_utils.get_pacific_date", return_value="2026-05-29"):
        handler.execute(event, config)
        handler.reply_flex.assert_called_once()
        args, kwargs = handler.reply_flex.call_args
        assert "設置選單" in args[2]
        
        # 驗證「設置玩家暱稱」已啟用，且對應指令為 #設置玩家暱稱
        flex_card = args[3]
        buttons_box = flex_card["body"]["contents"][1]
        btn_labels = [btn["action"]["label"] for btn in buttons_box["contents"] if btn["type"] == "button"]
        assert "設置玩家暱稱" in btn_labels
        
        nickname_btn = [btn for btn in buttons_box["contents"] if btn["type"] == "button" and btn["action"]["label"] == "設置玩家暱稱"][0]
        assert nickname_btn["action"]["text"] == "#設置玩家暱稱"

        # 驗證在休賽季「設置選秀時間」啟用
        assert "設置選秀時間" in btn_labels
        draft_time_btn = [btn for btn in buttons_box["contents"] if btn["type"] == "button" and btn["action"]["label"] == "設置選秀時間"][0]
        assert draft_time_btn["action"]["text"] == "#設置選秀時間"

        # 驗證在休賽季「設置開季時間」啟用
        assert "設置開季時間" in btn_labels
        season_time_btn = [btn for btn in buttons_box["contents"] if btn["type"] == "button" and btn["action"]["label"] == "設置開季時間"][0]
        assert season_time_btn["action"]["text"] == "#設置開季時間"

        # 驗證「更換聯盟ID (即將推出)」已不存在
        assert "更換聯盟ID (即將推出)" not in btn_labels

        # 驗證「設置獎金」按鈕存在，且位置在「設置玩家暱稱」之下，分隔線之上
        btn_labels = [btn["action"]["label"] for btn in buttons_box["contents"] if btn["type"] == "button"]
        assert "設置獎金" in btn_labels
        
        contents = buttons_box["contents"]
        idx_nickname = -1
        idx_prize = -1
        idx_separator = -1
        
        for idx, item in enumerate(contents):
            if item.get("type") == "button":
                label = item["action"].get("label")
                if label == "設置玩家暱稱":
                    idx_nickname = idx
                elif label == "設置獎金":
                    idx_prize = idx
            elif item.get("type") == "separator":
                idx_separator = idx
                
        assert idx_nickname != -1
        assert idx_prize != -1
        assert idx_separator != -1
        assert idx_nickname < idx_prize < idx_separator


def test_settings_handler_execute_inseason():
    handler = SettingsHandler()
    handler.reply_flex = MagicMock()

    event = MagicMock()
    config = MagicMock()

    with patch("src.handlers.settings_handler.load_config", return_value={"LEAGUE_ID": "12345"}), \
         patch("src.utils.security.security_manager.is_league_manager", return_value=True), \
         patch("src.utils.cache_utils.load_league_metadata", return_value={"end_date": "2026-04-12"}), \
         patch("src.utils.time_utils.get_pacific_date", return_value="2026-04-10"):
        handler.execute(event, config)
        handler.reply_flex.assert_called_once()
        args, kwargs = handler.reply_flex.call_args
        
        flex_card = args[3]
        buttons_box = flex_card["body"]["contents"][1]
        btn_labels = [btn["action"]["label"] for btn in buttons_box["contents"] if btn["type"] == "button"]
        
        # 驗證在非休賽季（賽季中）時，設定選單中完全不包含「設置選秀時間」與「設置開季時間」
        assert "設置選秀時間" not in btn_labels
        assert "設置選秀時間 (限休賽季)" not in btn_labels
        assert "設置開季時間" not in btn_labels
        assert "設置開季時間 (限休賽季)" not in btn_labels


def test_settings_handler_contains_remove_league_button():
    handler = SettingsHandler()
    handler.reply_flex = MagicMock()
    event = MagicMock()
    config = MagicMock()

    with patch("src.handlers.settings_handler.load_config", return_value={"LEAGUE_ID": "12345"}), \
         patch("src.utils.security.security_manager.is_league_manager", return_value=True), \
         patch("src.utils.cache_utils.load_league_metadata", return_value={"end_date": "2026-04-12"}), \
         patch("src.utils.time_utils.get_pacific_date", return_value="2026-04-10"):
        handler.execute(event, config)
        handler.reply_flex.assert_called_once()
        args = handler.reply_flex.call_args[0]
        flex_card = args[3]
        buttons_box = flex_card["body"]["contents"][1]
        remove_btn = [btn for btn in buttons_box["contents"] if btn["type"] == "button" and (btn["action"]["label"] == "移除聯盟ID (即將推出)" or btn["action"]["label"] == "移除聯盟ID")][0]
        assert remove_btn["action"]["text"] == "#移除聯盟ID"


def test_settings_roles_no_league_id_manager():
    handler = SettingsHandler()
    handler.reply_flex = MagicMock()
    event = MagicMock()
    config = MagicMock()

    with patch("src.handlers.settings_handler.load_config", return_value={"LEAGUE_ID": None}), \
         patch("src.utils.security.security_manager.is_manager", return_value=True):
        handler.execute(event, config)
        handler.reply_flex.assert_called_once()
        args = handler.reply_flex.call_args[0]
        flex_card = args[3]
        buttons_box = flex_card["body"]["contents"][1]
        btn_labels = [btn["action"]["label"] for btn in buttons_box["contents"] if btn["type"] == "button"]
        assert "設置聯盟 ID" in btn_labels


def test_settings_roles_no_league_id_non_manager():
    handler = SettingsHandler()
    handler.reply_flex = MagicMock()
    event = MagicMock()
    config = MagicMock()

    with patch("src.handlers.settings_handler.load_config", return_value={}), \
         patch("src.utils.security.security_manager.is_manager", return_value=False):
        handler.execute(event, config)
        handler.reply_flex.assert_called_once()
        args = handler.reply_flex.call_args[0]
        flex_card = args[3]
        # 當 buttons 為空時，不會有 buttons_box，body contents 只有一個元素 (header)
        assert len(flex_card["body"]["contents"]) == 1


def test_settings_roles_with_league_id_non_manager():
    handler = SettingsHandler()
    handler.reply_flex = MagicMock()
    event = MagicMock()
    config = MagicMock()

    with patch("src.handlers.settings_handler.load_config", return_value={"LEAGUE_ID": "12345"}), \
         patch("src.utils.security.security_manager.is_league_manager", return_value=False), \
         patch("src.utils.cache_utils.load_league_metadata", return_value={"end_date": "2026-04-12"}), \
         patch("src.utils.time_utils.get_pacific_date", return_value="2026-04-10"):
        handler.execute(event, config)
        handler.reply_flex.assert_called_once()
        args = handler.reply_flex.call_args[0]
        flex_card = args[3]
        buttons_box = flex_card["body"]["contents"][1]
        btn_labels = [btn["action"]["label"] for btn in buttons_box["contents"] if btn["type"] == "button"]
        
        # 普通白名單成員只會看到標準設定
        assert "設置玩家暱稱" in btn_labels
        assert "設置獎金" in btn_labels
        
        # 不應該看到管理員功能與移除聯盟ID
        assert "新增白名單成員" not in btn_labels
        assert "移除白名單成員" not in btn_labels
        assert "移除聯盟ID" not in btn_labels
        
        # 不應該有任何分隔線
        separators = [item for item in buttons_box["contents"] if item.get("type") == "separator"]
        assert len(separators) == 0


def test_settings_roles_with_league_id_manager():
    handler = SettingsHandler()
    handler.reply_flex = MagicMock()
    event = MagicMock()
    config = MagicMock()

    with patch("src.handlers.settings_handler.load_config", return_value={"LEAGUE_ID": "12345"}), \
         patch("src.utils.security.security_manager.is_league_manager", return_value=True), \
         patch("src.utils.cache_utils.load_league_metadata", return_value={"end_date": "2026-04-12"}), \
         patch("src.utils.time_utils.get_pacific_date", return_value="2026-04-10"):
        handler.execute(event, config)
        handler.reply_flex.assert_called_once()
        args = handler.reply_flex.call_args[0]
        flex_card = args[3]
        buttons_box = flex_card["body"]["contents"][1]
        btn_labels = [btn["action"]["label"] for btn in buttons_box["contents"] if btn["type"] == "button"]
        
        # 管理者可以看到標準設定與管理員功能
        assert "設置玩家暱稱" in btn_labels
        assert "設置獎金" in btn_labels
        assert "新增白名單成員" in btn_labels
        assert "移除白名單成員" in btn_labels
        assert "移除聯盟ID" in btn_labels
        
        # 應該有分隔線
        separators = [item for item in buttons_box["contents"] if item.get("type") == "separator"]
        assert len(separators) > 0




