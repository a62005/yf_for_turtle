import pytest
from datetime import datetime
import pytz
from src.utils.time_utils import get_fantasy_week, get_pacific_date

def test_get_fantasy_week():
    start_date = "2025-10-21" # A Tuesday
    # Week 1 starts from 10-21 until next Monday 00:00 PT
    
    tz = pytz.timezone("US/Pacific")
    # Same week Sunday 23:59 PT
    dt1 = tz.localize(datetime(2025, 10, 26, 23, 59, 59))
    assert get_fantasy_week(start_date, current_dt=dt1) == 1
    
    # Next week Monday 00:00 PT
    dt2 = tz.localize(datetime(2025, 10, 27, 0, 0, 0))
    assert get_fantasy_week(start_date, current_dt=dt2) == 2

def test_get_pacific_date():
    date_str = get_pacific_date()
    assert len(date_str) == 10
    datetime.strptime(date_str, "%Y-%m-%d")
