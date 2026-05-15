from datetime import datetime, timedelta
import pytz

def get_pacific_datetime():
    return datetime.now(pytz.timezone("US/Pacific"))

def get_pacific_date():
    return get_pacific_datetime().strftime("%Y-%m-%d")

def get_fantasy_week(start_date_str: str, current_dt=None) -> int:
    if current_dt is None:
        current_dt = get_pacific_datetime()
    
    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
    start_dt = pytz.timezone("US/Pacific").localize(start_dt)
    
    # Find the Monday 00:00 PT of the start week
    # start_dt.weekday(): 0=Monday, 1=Tuesday...
    start_monday = start_dt - timedelta(days=start_dt.weekday())
    start_monday = start_monday.replace(hour=0, minute=0, second=0, microsecond=0)
    
    delta = current_dt - start_monday
    week = (delta.days // 7) + 1
    return max(1, week)
