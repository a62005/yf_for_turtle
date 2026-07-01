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

def test_league_role_security_flow(tmp_path):
    admin_file = tmp_path / "super_admin.json"
    managers_file = tmp_path / "managers.json"
    roles_file = tmp_path / "league_roles.json"
    
    with open(admin_file, "w", encoding="utf-8") as f:
        json.dump({"super_admin": "Uadmin123"}, f)
        
    from src.utils.security import SecurityManager
    sm = SecurityManager(str(admin_file), str(managers_file), str(roles_file))
    
    # 測試全域管理員判定
    assert sm.is_manager("Uadmin123") is True # 超級管理員自動為管理員
    assert sm.is_manager("Umanager456") is False
    
    # 新增管理員並重新測試
    assert sm.add_manager("Umanager456", "小明") is True
    assert sm.is_manager("Umanager456") is True
    
    # 測試聯盟管理員判定
    assert sm.is_league_manager("Uadmin123", "nba.l.123") is True # 超級管理員自動為聯盟管理員
    assert sm.is_league_manager("Umanager456", "nba.l.123") is False
    
    # 設定聯盟經理並測試
    assert sm.set_league_owner("nba.l.123", "Umanager456") is True
    assert sm.is_league_manager("Umanager456", "nba.l.123") is True
    
    # 測試聯盟白名單成員判定
    assert sm.is_league_whitelisted("Uadmin123", "nba.l.123") is True # 超級管理員自動為白名單成員
    assert sm.is_league_whitelisted("Umanager456", "nba.l.123") is True # 聯盟管理員自動為白名單成員
    assert sm.is_league_whitelisted("Uuser789", "nba.l.123") is False
    
    # 新增成員到該聯盟的白名單
    assert sm.add_to_league_whitelist("nba.l.123", "Uuser789", "大雄") is True
    assert sm.is_league_whitelisted("Uuser789", "nba.l.123") is True
    
    # 移除白名單成員
    assert sm.remove_from_league_whitelist("nba.l.123", "Uuser789") is True
    assert sm.is_league_whitelisted("Uuser789", "nba.l.123") is False

