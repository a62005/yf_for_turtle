import pytest
from src.visualizer.flex_builder import (
    get_status_color,
    build_stats_list_card,
    build_matchup_comparison_card,
    build_status_badge_list_card,
    build_button_menu_card
)

def test_get_status_color():
    assert get_status_color("O") == "#922B21"
    assert get_status_color("inj") == "#922B21"
    assert get_status_color("DTD") == "#E67E22"
    assert get_status_color("GTD") == "#F1C40F"
    assert get_status_color("UNKNOWN") == "#7F8C8D"
    assert get_status_color(None) == "#7F8C8D"


def test_build_stats_list_card():
    sections = [
        {
            "header": "2026-06-24",
            "rows": [
                ("FGM/A", "5/10"),
                ("FG%", 50.0) # test float to string conversion as well
            ]
        }
    ]
    card = build_stats_list_card("Player Stats", "Season Average", sections)
    assert card["type"] == "bubble"
    body_contents = card["body"]["contents"]
    # Check header
    header = body_contents[0]
    assert header["type"] == "box"
    assert header["contents"][0]["text"] == "Player Stats"
    assert header["contents"][0]["size"] == "xl"
    assert header["contents"][1]["text"] == "Season Average"
    assert header["contents"][1]["size"] == "sm"
    
    # Check section box
    section_box = body_contents[1]
    assert section_box["contents"][0]["text"] == "2026-06-24"
    assert section_box["contents"][0]["size"] == "md"
    
    rows_box = section_box["contents"][1]
    assert len(rows_box["contents"]) == 2
    # Row 0
    assert rows_box["contents"][0]["contents"][0]["text"] == "FGM/A"
    assert rows_box["contents"][0]["contents"][0]["color"] == "#666666"
    assert rows_box["contents"][0]["contents"][1]["text"] == "5/10"
    assert rows_box["contents"][0]["contents"][1]["weight"] == "bold"
    assert rows_box["contents"][0]["contents"][1]["align"] == "end"
    
    # Row 1 (float converted to string)
    assert rows_box["contents"][1]["contents"][0]["text"] == "FG%"
    assert rows_box["contents"][1]["contents"][1]["text"] == "50.0"


def test_build_matchup_comparison_card_standard():
    card = build_matchup_comparison_card("WEEK 6 MATCHUP", "Standard Subtitle", [])
    assert card["type"] == "bubble"
    header = card["body"]["contents"][0]
    assert header["contents"][0]["text"] == "WEEK 6 MATCHUP"
    assert header["contents"][1]["text"] == "Standard Subtitle"


def test_build_matchup_comparison_card_special_header():
    subtitle_dict = {
        "my_nickname": "My Team",
        "my_official": "My Official Co.",
        "opp_nickname": "Opp Team",
        "opp_official": "Opp Official Co.",
        "wins": 5,
        "losses": 4
    }
    comparison_rows = [
        ("FGM/A", "25/50", "30/60", None, True),
        ("FG%", "50.0%", "50.0%", "tie", False),
        ("PTS", "110", "95", "my_win", False),
        ("ST", "10", "12", "opp_win", False)
    ]
    
    card = build_matchup_comparison_card("WEEK 6 MATCHUP", subtitle_dict, comparison_rows)
    assert card["type"] == "bubble"
    body_contents = card["body"]["contents"]
    
    # Check matchup header structure
    title_box = body_contents[0]
    assert title_box["text"] == "WEEK 6 MATCHUP"
    assert title_box["size"] == "xxs"
    assert title_box["color"] == "#cccccc"
    
    nickname_box = body_contents[1]
    assert nickname_box["contents"][0]["text"] == "My Team"
    assert nickname_box["contents"][1]["text"] == "VS"
    assert nickname_box["contents"][2]["text"] == "Opp Team"
    
    team_name_box = body_contents[2]
    assert team_name_box["contents"][0]["text"] == "My Official Co."
    assert team_name_box["contents"][2]["text"] == "Opp Official Co."
    
    score_box = body_contents[3]
    # scores (my_win = wins 5 > losses 4, so wins should have size 20px, losses size 18px)
    assert score_box["contents"][0]["text"] == "5"
    assert score_box["contents"][0]["size"] == "20px"
    assert score_box["contents"][2]["text"] == "4"
    assert score_box["contents"][2]["size"] == "18px"
    
    # Check comparison rows
    rows_box = body_contents[4]
    # Row 0: FGM/A is aux row (value sizes should be xs)
    row0 = rows_box["contents"][0]
    assert row0["contents"][0]["text"] == "25/50"
    assert row0["contents"][0]["size"] == "xs"
    assert row0["contents"][1]["text"] == "FGM/A"
    assert row0["contents"][1]["size"] == "xs"
    assert row0["contents"][2]["text"] == "30/60"
    assert row0["contents"][2]["size"] == "xs"
    
    # Row 1: FG% tie
    row1 = rows_box["contents"][1]
    assert row1["contents"][0]["text"] == "50.0%"
    assert row1["contents"][0]["size"] == "14px"
    assert row1["contents"][1]["text"] == "FG%"
    
    # Row 2: PTS my_win (my val bold 16px, opp val regular 14px)
    row2 = rows_box["contents"][2]
    assert row2["contents"][0]["text"] == "110"
    assert row2["contents"][0]["size"] == "16px"
    assert row2["contents"][0]["weight"] == "bold"
    assert row2["contents"][2]["text"] == "95"
    assert row2["contents"][2]["size"] == "14px"
    
    # Row 3: ST should translate to STL, opp_win
    row3 = rows_box["contents"][3]
    assert row3["contents"][1]["text"] == "STL"
    assert row3["contents"][0]["text"] == "10"
    assert row3["contents"][0]["size"] == "14px"
    assert row3["contents"][2]["text"] == "12"
    assert row3["contents"][2]["size"] == "16px"
    assert row3["contents"][2]["weight"] == "bold"


def test_build_status_badge_list_card():
    # Test empty items
    card_empty = build_status_badge_list_card("Injury Report", "None", [])
    assert card_empty["body"]["contents"][1]["contents"][0]["text"] == "🟢 目前全隊球員皆健康！"
    
    # Test items
    items = [
        ("S. Curry", "Knee", "O", "#922B21"),
        ("L. James", None, "DTD", "#E67E22")
    ]
    card = build_status_badge_list_card("Injury Report", "Active", items)
    body_contents = card["body"]["contents"]
    rows_box = body_contents[1]
    
    # Check S. Curry
    row0 = rows_box["contents"][0]
    assert row0["contents"][0]["text"] == "S. Curry - Knee"
    badge0 = row0["contents"][1]
    assert badge0["backgroundColor"] == "#922B21"
    assert badge0["contents"][0]["text"] == "O"
    
    # Check L. James
    row1 = rows_box["contents"][1]
    assert row1["contents"][0]["text"] == "L. James"
    badge1 = row1["contents"][1]
    assert badge1["backgroundColor"] == "#E67E22"
    assert badge1["contents"][0]["text"] == "DTD"


def test_build_button_menu_card():
    buttons = [
        ("陳威", "#對戰 陳威"),
        ("小明", "#對戰 小明")
    ]
    card = build_button_menu_card("Matchup Menu", "Select Opponent", buttons)
    body_contents = card["body"]["contents"]
    buttons_box = body_contents[1]
    assert len(buttons_box["contents"]) == 2
    btn0 = buttons_box["contents"][0]
    assert btn0["type"] == "button"
    assert btn0["style"] == "secondary"
    assert btn0["action"]["label"] == "陳威"
    assert btn0["action"]["text"] == "#對戰 陳威"


def test_all_cards_schema_validation():
    import json
    from linebot.v3.messaging import FlexContainer
    
    # 1. Stats card
    sections = [{"header": "2026-06-24", "rows": [("FGM/A", "5/10"), ("FG%", "50.0%")]}]
    card1 = build_stats_list_card("Player Stats", "Season Average", sections)
    FlexContainer.from_json(json.dumps(card1))
    
    # 2. Matchup card
    subtitle_dict = {
        "my_nickname": "My Team", "my_official": "My Co.",
        "opp_nickname": "Opp Team", "opp_official": "Opp Co.",
        "wins": 5, "losses": 4
    }
    comparison_rows = [("FGM/A", "25/50", "30/60", None, True), ("FG%", "50.0%", "50.0%", "tie", False)]
    card2 = build_matchup_comparison_card("WEEK 6 MATCHUP", subtitle_dict, comparison_rows)
    FlexContainer.from_json(json.dumps(card2))
    
    # 3. Injury card
    items = [("S. Curry", "Knee", "O", "#922B21")]
    card3 = build_status_badge_list_card("Injury Report", "Active", items)
    FlexContainer.from_json(json.dumps(card3))
    
    # 4. Button card
    buttons = [("陳威", "#對戰 陳威")]
    card4 = build_button_menu_card("Matchup Menu", "Select", buttons)
    FlexContainer.from_json(json.dumps(card4))


def test_build_button_menu_card_with_empty_text():
    buttons = [
        ("設置選秀時間 (即將推出)", ""),
        ("更換聯盟ID (即將推出)", None)
    ]
    card = build_button_menu_card("Settings Menu", "Select Option", buttons)
    body_contents = card["body"]["contents"]
    buttons_box = body_contents[1]
    assert len(buttons_box["contents"]) == 2
    
    btn0 = buttons_box["contents"][0]
    assert btn0["type"] == "button"
    assert btn0["action"]["type"] == "postback"
    assert btn0["action"]["label"] == "設置選秀時間 (即將推出)"
    assert btn0["action"]["data"] == "action=ignore"
    
    btn1 = buttons_box["contents"][1]
    assert btn1["type"] == "button"
    assert btn1["action"]["type"] == "postback"
    assert btn1["action"]["label"] == "更換聯盟ID (即將推出)"
    assert btn1["action"]["data"] == "action=ignore"


