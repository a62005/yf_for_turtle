import time

_sessions = {}  # 格式: { user_id: { "team_id": str, "expire_at": float } }

def set_nickname_session(user_id: str, team_id: str, duration_sec: int = 60) -> None:
    _sessions[user_id] = {
        "team_id": team_id,
        "expire_at": time.time() + duration_sec
    }

def get_nickname_session(user_id: str) -> dict | None:
    session = _sessions.get(user_id)
    if not session:
        return None
    if time.time() > session["expire_at"]:
        del _sessions[user_id]
        return None
    return session

def clear_nickname_session(user_id: str) -> None:
    if user_id in _sessions:
        del _sessions[user_id]
