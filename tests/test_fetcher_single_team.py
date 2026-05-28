import pytest
from unittest.mock import MagicMock
import xml.etree.ElementTree as ET
from src.fetcher import YahooFantasyFetcher

# 模擬的 Yahoo Team Stats XML 回傳數據
MOCK_TEAM_STATS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<fantasy_content xmlns="http://fantasysports.yahooapis.com/fantasy/v2/base.rng">
  <team>
    <team_key>nba.l.12345.t.1</team_key>
    <name>Vigo's Superteam</name>
    <team_stats>
      <stats>
        <stat><stat_id>4</stat_id><value>14</value></stat>
        <stat><stat_id>3</stat_id><value>24</value></stat>
        <stat><stat_id>5</stat_id><value>0.583</value></stat>
        <stat><stat_id>7</stat_id><value>3</value></stat>
        <stat><stat_id>6</stat_id><value>4</value></stat>
        <stat><stat_id>8</stat_id><value>0.750</value></stat>
        <stat><stat_id>10</stat_id><value>4</value></stat>
        <stat><stat_id>12</stat_id><value>35</value></stat>
        <stat><stat_id>15</stat_id><value>9</value></stat>
        <stat><stat_id>16</stat_id><value>12</value></stat>
        <stat><stat_id>17</stat_id><value>2</value></stat>
        <stat><stat_id>18</stat_id><value>1</value></stat>
        <stat><stat_id>19</stat_id><value>3</value></stat>
      </stats>
    </team_stats>
  </team>
</fantasy_content>
"""

def test_parse_team_stats_xml():
    fetcher = YahooFantasyFetcher(team_mapping={"1": "韋哥"})
    res = fetcher._parse_team_stats_xml(MOCK_TEAM_STATS_XML)
    
    assert res["team_name"] == "Vigo's Superteam"
    stats = res["stats"]
    assert stats["stat_4"] == "14" # FGM
    assert stats["stat_3"] == "24" # FGA
    assert stats["FG%"] == "0.583"
    assert stats["stat_7"] == "3"  # FTM
    assert stats["stat_6"] == "4"  # FTA
    assert stats["FT%"] == "0.750"
    assert stats["3PTM"] == "4"
    assert stats["PTS"] == "35"
    assert stats["REB"] == "9"
    assert stats["AST"] == "12"
    assert stats["ST"] == "2"
    assert stats["BLK"] == "1"
    assert stats["TO"] == "3"

def test_fetch_single_team_stats_by_url(mocker):
    # Mock self.ctx.make_request 回傳模擬的 XML
    fetcher = YahooFantasyFetcher(team_mapping={"1": "韋哥"})
    mock_make_request = mocker.patch.object(fetcher.ctx, "make_request", return_value=MOCK_TEAM_STATS_XML)
    
    res = fetcher.fetch_single_team_stats_by_url("nba.l.12345.t.1", "date", "2026-05-28")
    
    # 驗證是否打對了 Yahoo API Endpoint
    mock_make_request.assert_called_once_with("team/nba.l.12345.t.1/stats;type=date;date=2026-05-28")
    assert res["team_name"] == "Vigo's Superteam"
    assert res["stats"]["PTS"] == "35"
