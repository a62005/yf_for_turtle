import pytest
from src.fetcher import YahooFantasyFetcher

def test_fetch_matchups_parsing(mocker):
    mock_ctx = mocker.patch("src.fetcher.yahoofantasy.Context").return_value
    
    mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <fantasy_content xmlns="http://fantasysports.yahooapis.com/fantasy/v2/base.rng">
      <league>
        <scoreboard>
          <matchups>
            <matchup>
              <teams>
                <team>
                  <team_id>1</team_id>
                  <name>Vigo's Superteam</name>
                  <team_stats>
                    <stats>
                      <stat><stat_id>4</stat_id><value>180</value></stat>
                      <stat><stat_id>3</stat_id><value>350</value></stat>
                      <stat><stat_id>5</stat_id><value>0.514</value></stat>
                      <stat><stat_id>7</stat_id><value>20</value></stat>
                      <stat><stat_id>6</stat_id><value>25</value></stat>
                      <stat><stat_id>8</stat_id><value>0.800</value></stat>
                      <stat><stat_id>10</stat_id><value>35</value></stat>
                      <stat><stat_id>12</stat_id><value>450</value></stat>
                      <stat><stat_id>15</stat_id><value>110</value></stat>
                      <stat><stat_id>16</stat_id><value>95</value></stat>
                      <stat><stat_id>17</stat_id><value>25</value></stat>
                      <stat><stat_id>18</stat_id><value>12</value></stat>
                      <stat><stat_id>19</stat_id><value>32</value></stat>
                    </stats>
                  </team_stats>
                </team>
                <team>
                  <team_id>2</team_id>
                  <name>Jerry's Awesome</name>
                  <team_stats>
                    <stats>
                      <stat><stat_id>4</stat_id><value>165</value></stat>
                      <stat><stat_id>3</stat_id><value>340</value></stat>
                      <stat><stat_id>5</stat_id><value>0.485</value></stat>
                      <stat><stat_id>7</stat_id><value>15</value></stat>
                      <stat><stat_id>6</stat_id><value>20</value></stat>
                      <stat><stat_id>8</stat_id><value>0.750</value></stat>
                      <stat><stat_id>10</stat_id><value>42</value></stat>
                      <stat><stat_id>12</stat_id><value>410</value></stat>
                      <stat><stat_id>15</stat_id><value>125</value></stat>
                      <stat><stat_id>16</stat_id><value>80</value></stat>
                      <stat><stat_id>17</stat_id><value>20</value></stat>
                      <stat><stat_id>18</stat_id><value>18</value></stat>
                      <stat><stat_id>19</stat_id><value>38</value></stat>
                    </stats>
                  </team_stats>
                </team>
              </teams>
            </matchup>
          </matchups>
        </scoreboard>
      </league>
    </fantasy_content>
    """
    mock_ctx.make_request.return_value = mock_xml
    
    fetcher = YahooFantasyFetcher(team_mapping={"1": "韋哥", "2": "Jerry"})
    matchups = fetcher.fetch_matchups("12345", 24)
    
    assert len(matchups) == 1
    m = matchups[0]
    assert m["team1"]["team_id"] == "1"
    assert m["team1"]["name"] == "韋哥"
    assert m["team1"]["official_name"] == "Vigo's Superteam"
    assert m["team1"]["stats"]["FG%"] == "0.514"
    assert m["team1"]["stats"]["PTS"] == "450"
    assert m["team1"]["stats"]["FGM/FGA"] == "180/350"
    
    assert m["team2"]["team_id"] == "2"
    assert m["team2"]["name"] == "Jerry"
    assert m["team2"]["stats"]["FTM/FTA"] == "15/20"
