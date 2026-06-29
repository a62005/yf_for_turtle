import os
import json
import tempfile
import shutil
import pytest
import xml.etree.ElementTree as ET
from src.fetcher import YahooFantasyFetcher

mock_settings_xml = """<?xml version="1.0" encoding="UTF-8"?>
<fantasy_content xmlns="http://fantasysports.yahooapis.com/fantasy/v2/base.rng">
  <league>
    <settings>
      <stat_categories>
        <stats>
          <stat>
            <stat_id>12</stat_id>
            <name>Points</name>
            <display_name>PTS</display_name>
            <sort_order>1</sort_order>
          </stat>
          <stat>
            <stat_id>19</stat_id>
            <name>Turnovers</name>
            <display_name>TO</display_name>
            <sort_order>0</sort_order>
          </stat>
        </stats>
      </stat_categories>
    </settings>
  </league>
</fantasy_content>
"""

def test_fetch_and_cache_settings(mocker):
    temp_dir = tempfile.mkdtemp()
    mocker.patch("src.utils.path_utils.DATA_DIR", temp_dir)
    
    mock_ctx = mocker.patch("src.fetcher.yahoofantasy.Context").return_value
    mock_ctx.make_request.return_value = mock_settings_xml
    
    fetcher = YahooFantasyFetcher(league_id="nba.l.18457")
    fetcher.ctx = mock_ctx
    
    stats_list = fetcher.sync_league_settings("nba.l.18457")
    assert len(stats_list) == 2
    assert stats_list[0]["display_name"] == "PTS"
    assert stats_list[0]["sort_order"] == 1
    assert stats_list[1]["display_name"] == "TO"
    assert stats_list[1]["sort_order"] == 0
    
    # Check cached metadata file contains categories
    meta_file = os.path.join(temp_dir, "league", "nba.l.18457", "metadata.json")
    assert os.path.exists(meta_file)
    with open(meta_file, "r") as f:
        meta = json.load(f)
    assert "stat_categories" in meta
    assert meta["stat_categories"][0]["display_name"] == "PTS"
    
    shutil.rmtree(temp_dir)
