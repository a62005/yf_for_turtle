import os
import json
import logging

class SecurityManager:
    def __init__(self, super_admin_path: str = "data/security/super_admin.json",
                 managers_path: str = "data/security/managers.json",
                 league_roles_path: str = "data/security/league_roles.json",
                 whitelist_path: str = "data/security/whitelist.json"):
        self.super_admin_path = super_admin_path
        self.managers_path = managers_path
        self.league_roles_path = league_roles_path
        self.whitelist_path = whitelist_path

        # For backward compatibility, if managers_path is passed as the old whitelist_path
        # (e.g. in test_security_manager_basic_flow), we map it correctly.
        if "whitelist" in self.managers_path or not self.managers_path.endswith("managers.json"):
            self.whitelist_path = self.managers_path

    def _load_json(self, path: str, default: dict) -> dict:
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(default, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logging.error(f"[SecurityManager] 寫入預設檔案失敗 {path}: {e}")
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"[SecurityManager] 讀取檔案失敗 {path}: {e}")
            return default

    def _save_json(self, path: str, data: dict) -> bool:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logging.error(f"[SecurityManager] 儲存檔案失敗 {path}: {e}")
            return False

    def is_super_admin(self, user_id: str | None) -> bool:
        if not user_id:
            return False
        data = self._load_json(self.super_admin_path, {"super_admin": ""})
        return data.get("super_admin") == user_id

    def is_manager(self, user_id: str | None) -> bool:
        if not user_id:
            return False
        if self.is_super_admin(user_id):
            return True
        data = self._load_json(self.managers_path, {"managers": {}})
        return user_id in data.get("managers", {})

    def is_league_manager(self, user_id: str | None, league_id: str | None) -> bool:
        if not user_id:
            return False
        if self.is_super_admin(user_id):
            return True
        if not league_id:
            return False
        data = self._load_json(self.league_roles_path, {})
        league_data = data.get(league_id) or {}
        return league_data.get("manager") == user_id

    def is_league_whitelisted(self, user_id: str | None, league_id: str | None) -> bool:
        if not user_id:
            return False
        if self.is_super_admin(user_id):
            return True
        if not league_id:
            return False
        if self.is_league_manager(user_id, league_id):
            return True
        data = self._load_json(self.league_roles_path, {})
        league_data = data.get(league_id) or {}
        return user_id in league_data.get("whitelist", {})

    def is_whitelisted(self, user_id: str | None) -> bool:
        if not user_id:
            return False
        if self.is_super_admin(user_id):
            return True
        
        # 1. 嘗試聯盟白名單判定
        try:
            from src.config import load_config
            league_id = load_config().get("LEAGUE_ID")
        except Exception:
            league_id = None
            
        if league_id and self.is_league_whitelisted(user_id, league_id):
            return True
            
        # 2. 相容舊版全域白名單判定 (whitelist.json)
        if self.whitelist_path and os.path.exists(self.whitelist_path):
            try:
                with open(self.whitelist_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if "whitelist" in data and user_id in data["whitelist"]:
                    return True
            except Exception:
                pass
        return False

    def add_to_whitelist(self, user_id: str) -> bool:
        path = self.whitelist_path
        data = self._load_json(path, {"whitelist": []})
        whitelist = data.setdefault("whitelist", [])
        if user_id not in whitelist:
            whitelist.append(user_id)
            return self._save_json(path, data)
        return True

    def add_manager(self, user_id: str, name: str) -> bool:
        data = self._load_json(self.managers_path, {"managers": {}})
        managers = data.setdefault("managers", {})
        managers[user_id] = name
        return self._save_json(self.managers_path, data)

    def set_league_owner(self, league_id: str, manager_id: str) -> bool:
        data = self._load_json(self.league_roles_path, {})
        league_data = data.setdefault(league_id, {"manager": "", "whitelist": {}})
        league_data["manager"] = manager_id
        return self._save_json(self.league_roles_path, data)

    def set_league_authorized(self, league_id: str, authorized: bool) -> bool:
        data = self._load_json(self.league_roles_path, {})
        league_data = data.setdefault(league_id, {"manager": "", "whitelist": {}})
        league_data["authorized"] = authorized
        return self._save_json(self.league_roles_path, data)

    def add_to_league_whitelist(self, league_id: str, user_id: str, name: str) -> bool:
        data = self._load_json(self.league_roles_path, {})
        league_data = data.setdefault(league_id, {"manager": "", "whitelist": {}})
        whitelist = league_data.setdefault("whitelist", {})
        whitelist[user_id] = name
        return self._save_json(self.league_roles_path, data)

    def remove_from_league_whitelist(self, league_id: str, user_id: str) -> bool:
        data = self._load_json(self.league_roles_path, {})
        if league_id in data and "whitelist" in data[league_id]:
            if user_id in data[league_id]["whitelist"]:
                del data[league_id]["whitelist"][user_id]
                return self._save_json(self.league_roles_path, data)
        return True

# 導出全域單一實例供各模組使用
security_manager = SecurityManager()
