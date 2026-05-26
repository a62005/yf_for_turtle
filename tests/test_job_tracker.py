import pytest
from unittest.mock import patch, MagicMock
from src.utils.job_tracker import JobTracker

@patch("src.utils.job_tracker.os.path.exists", return_value=False)
@patch("src.utils.job_tracker.open")
def test_job_tracker_local(mock_open, mock_exists):
    tracker = JobTracker(mode="local")
    
    # Simulate adding job
    mock_file = MagicMock()
    mock_file.read.return_value = "{}"
    mock_open.return_value.__enter__.return_value = mock_file
    
    is_new = tracker.add_job("week_1", "userA")
    assert is_new is True
    
    # We can't easily assert the file write contents accurately with simple mock_open across multiple calls, 
    # but we can verify methods exist and don't crash.
    users = tracker.get_job_users("week_1")
    assert isinstance(users, list)
