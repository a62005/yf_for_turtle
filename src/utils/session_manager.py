import time

_sessions = {}  # 格式: { (user_id, session_type): { "data": any, "expire_at": float } }

def set_session(user_id: str, session_type: str, data: any, duration_sec: int = 60) -> None:
    _sessions[(user_id, session_type)] = {
        "data": data,
        "expire_at": time.time() + duration_sec
    }

def get_session(user_id: str, session_type: str) -> any | None:
    key = (user_id, session_type)
    session = _sessions.get(key)
    if not session:
        return None
    if time.time() > session["expire_at"]:
        del _sessions[key]
        return None
    return session["data"]

def clear_session(user_id: str, session_type: str) -> None:
    key = (user_id, session_type)
    if key in _sessions:
        del _sessions[key]

# 特定類型的會話 Helper 函式

def set_nickname_session(user_id: str, team_id: str, duration_sec: int = 60) -> None:
    set_session(user_id, "nickname", {"team_id": team_id}, duration_sec)

def get_nickname_session(user_id: str) -> dict | None:
    key = (user_id, "nickname")
    session = _sessions.get(key)
    if not session:
        return None
    if time.time() > session["expire_at"]:
        del _sessions[key]
        return None
    result = dict(session["data"])
    result["expire_at"] = session["expire_at"]
    return result

def clear_nickname_session(user_id: str) -> None:
    clear_session(user_id, "nickname")

def set_draft_time_session(user_id: str, data: any, duration_sec: int = 60) -> None:
    set_session(user_id, "draft_time", data, duration_sec)

def get_draft_time_session(user_id: str) -> any | None:
    return get_session(user_id, "draft_time")

def clear_draft_time_session(user_id: str) -> None:
    clear_session(user_id, "draft_time")
