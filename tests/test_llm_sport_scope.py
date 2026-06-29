import pytest
from src.llm.llm_agent import LLMAgent

def test_player_fuzzy_search_sport_context_mlb(mocker):
    agent = LLMAgent()
    
    mock_provider = mocker.patch.object(agent, "provider")
    
    # 第一次回傳 False 觸發搜尋，第二次回傳球員資料
    mock_provider.generate_json.side_effect = [
        {"is_known_player": False},
        {
            "is_known_player": True,
            "english_name": "Shohei Ohtani",
            "chinese_name": "大谷翔平",
            "team": "LAD",
            "jersey_number": "17"
        }
    ]
    
    mock_google_search = mocker.patch.object(agent, "google_search", return_value=["LAD player"])
    
    # Fuzzy search under MLB context
    res = agent.player_fuzzy_search("大谷", sport="mlb")
    assert res["english_name"] == "Shohei Ohtani"
    
    # Check that search was called with MLB prefix
    mock_google_search.assert_called_once_with('MLB "大谷"')
    
    # Check that prompt text contains MLB and 棒球專家
    args, kwargs = mock_provider.generate_json.call_args
    prompt_text = args[0]
    assert "MLB" in prompt_text
    assert "棒球專家" in prompt_text

def test_player_fuzzy_search_sport_context_nba(mocker):
    agent = LLMAgent()
    
    mock_provider = mocker.patch.object(agent, "provider")
    
    # 第一次回傳 False 觸發搜尋，第二次回傳球員資料
    mock_provider.generate_json.side_effect = [
        {"is_known_player": False},
        {
            "is_known_player": True,
            "english_name": "Stephen Curry",
            "chinese_name": "史蒂芬·柯瑞",
            "team": "GSW",
            "jersey_number": "30"
        }
    ]
    
    mock_google_search = mocker.patch.object(agent, "google_search", return_value=["GSW player"])
    
    # Fuzzy search under NBA context
    res = agent.player_fuzzy_search("咖哩", sport="nba")
    assert res["english_name"] == "Stephen Curry"
    
    # Check that search was called with NBA prefix
    mock_google_search.assert_called_once_with('NBA "咖哩"')
    
    # Check that prompt text contains NBA and 籃球專家
    args, kwargs = mock_provider.generate_json.call_args
    prompt_text = args[0]
    assert "NBA" in prompt_text
    assert "籃球專家" in prompt_text
