import os
import json
import logging

class SecurityManager:
    def __init__(self, super_admin_path: str = "data/security/super_admin.json", whitelist_path: str = "data/security/whitelist.json"):
        self.super_admin_path = super_admin_path
        self.whitelist_path = whitelist_path

    def _load_json(self, path: str, default: dict) -> dict:
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(default, f, indent=2)
            except Exception as e:
                logging.error(f"[SecurityManager] 寫入預設檔案失敗 {path}: {e}")
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"[SecurityManager] 讀取檔案失敗 {path}: {e}")
            return default

    def is_super_admin(self, user_id: str | None) -> bool:
        if not user_id:
            return False
        data = self._load_json(self.super_admin_path, {"super_admin": ""})
        return data.get("super_admin") == user_id

    def is_whitelisted(self, user_id: str | None) -> bool:
        if not user_id:
            return False
        if self.is_super_admin(user_id):
            return True
        data = self._load_json(self.whitelist_path, {"whitelist": []})
        return user_id in data.get("whitelist", [])

    def add_to_whitelist(self, user_id: str) -> bool:
        data = self._load_json(self.whitelist_path, {"whitelist": []})
        whitelist = data.get("whitelist", [])
        if user_id not in whitelist:
            whitelist.append(user_id)
            data["whitelist"] = whitelist
            try:
                os.makedirs(os.path.dirname(self.whitelist_path), exist_ok=True)
                with open(self.whitelist_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                return True
            except Exception as e:
                logging.error(f"[SecurityManager] 寫入白名單失敗 {self.whitelist_path}: {e}")
                return False
        return True

# 導出全域單一實例供各模組使用
security_manager = SecurityManager()
