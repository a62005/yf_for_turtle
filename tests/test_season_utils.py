import pytest
from unittest.mock import MagicMock, patch
from src.utils.season_utils import generate_dates, sync_season_metadata

def test_generate_dates():
    dates = generate_dates("2025-10-21", "2025-10-23")
    assert dates == ["2025-10-21", "2025-10-22", "2025-10-23"]

@patch("src.utils.season_utils.load_league_metadata")
@patch("src.utils.season_utils.save_league_metadata")
def test_sync_season_metadata_incomplete_base(mock_save, mock_load):
    fetcher = MagicMock()
    # Mock returning incomplete data
    fetcher.fetch_league_metadata.return_value = {"league_id": "nba.l.123"}
    
    sync_season_metadata(fetcher, "123")
    
    # Should save what it got and return early
    mock_load.assert_called_once_with("123")
    mock_save.assert_called_once_with({"league_id": "nba.l.123"}, "123")
    assert fetcher.fetch_week_end_date.call_count == 0

@patch("src.utils.season_utils.load_league_metadata")
@patch("src.utils.season_utils.save_league_metadata")
def test_sync_season_metadata_needs_update(mock_save, mock_load):
    fetcher = MagicMock()
    fetcher.fetch_league_metadata.return_value = {
        "league_id": "nba.l.123",
        "start_date": "2025-10-21",
        "end_week": 2
    }
    # Mock load to return empty/old data
    mock_load.return_value = {}
    
    # Mock week end dates
    fetcher.fetch_week_end_date.side_effect = ["2025-10-27", "2025-11-03"]
    
    sync_season_metadata(fetcher, "123")
    
    mock_load.assert_called_once_with("123")
    assert fetcher.fetch_week_end_date.call_count == 2
    mock_save.assert_called_once_with(mock_save.call_args[0][0], "123")
    
    saved_meta = mock_save.call_args[0][0]
    assert saved_meta["week_dates"] == {"1": "2025-10-27", "2": "2025-11-03"}
    # 2025-10-21 to 2025-10-27 is 7 days
    # 2025-10-28 to 2025-11-03 is 7 days
    assert len(saved_meta["date_to_week"]) == 14
    assert saved_meta["date_to_week"]["2025-10-21"] == 1
    assert saved_meta["date_to_week"]["2025-10-27"] == 1
    assert saved_meta["date_to_week"]["2025-10-28"] == 2
    assert saved_meta["date_to_week"]["2025-11-03"] == 2

@patch("src.utils.season_utils.load_league_metadata")
@patch("src.utils.season_utils.save_league_metadata")
def test_sync_season_metadata_no_update_needed(mock_save, mock_load):
    fetcher = MagicMock()
    meta = {
        "league_id": "nba.l.123",
        "start_date": "2025-10-21",
        "end_week": 2
    }
    fetcher.fetch_league_metadata.return_value = meta
    
    # Mock load to return fully populated data
    mock_load.return_value = {
        "league_id": "nba.l.123",
        "week_dates": {"1": "2025-10-27", "2": "2025-11-03"},
        "date_to_week": {"2025-10-21": 1}
    }
    
    sync_season_metadata(fetcher, "123")
    
    # Should not fetch week end dates again
    mock_load.assert_called_once_with("123")
    assert fetcher.fetch_week_end_date.call_count == 0
    mock_save.assert_called_once_with(mock_save.call_args[0][0], "123")
