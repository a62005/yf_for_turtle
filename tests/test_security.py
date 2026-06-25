import os
import json
import pytest
from src.utils.security import SecurityManager

def test_security_manager_basic_flow(tmp_path):
    admin_file = tmp_path / "super_admin.json"
    whitelist_file = tmp_path / "whitelist.json"
    
    # 寫入初始測試資料
    with open(admin_file, "w", encoding="utf-8") as f:
        json.dump({"super_admin": "Uadmin123"}, f)
    with open(whitelist_file, "w", encoding="utf-8") as f:
        json.dump({"whitelist": ["Uuser456"]}, f)
        
    sm = SecurityManager(str(admin_file), str(whitelist_file))
    
    # 測試超級管理員判定
    assert sm.is_super_admin("Uadmin123") is True
    assert sm.is_super_admin("Uuser456") is False
    assert sm.is_super_admin(None) is False
    
    # 測試白名單判定（超級管理員自動視為在白名單中）
    assert sm.is_whitelisted("Uadmin123") is True
    assert sm.is_whitelisted("Uuser456") is True
    assert sm.is_whitelisted("Uother789") is False
    assert sm.is_whitelisted(None) is False
    
    # 測試新增白名單
    assert sm.add_to_whitelist("Uother789") is True
    assert sm.is_whitelisted("Uother789") is True
    
    # 再次確認檔案被成功更新
    with open(whitelist_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "Uother789" in data["whitelist"]
