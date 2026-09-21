import os
import pytest
from unittest.mock import patch
import json
from src.utils.audit_logger import (
    get_audit_logger,
    record_data_change,
    get_audit_log_path,
    save_json_file,
    delete_data_file,
)

def test_record_data_change_writes_formatted_log(tmp_path):
    test_logs_dir = tmp_path / "logs"
    with patch("src.utils.path_utils.LOGS_DIR", str(test_logs_dir)):
        log_file = get_audit_log_path()
        record_data_change(
            action="CREATE",
            filepath="data/league/nba/123/stats.json",
            size=1024,
            caller_tag="test_module:test_func"
        )
        
        assert os.path.exists(log_file)
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert "[DATA_AUDIT]" in content
            assert "action=CREATE" in content
            assert "path=league/nba/123/stats.json" in content
            assert "size=1024B" in content
            assert "caller=test_module:test_func" in content

def test_audit_logger_rotation(tmp_path):
    test_logs_dir = tmp_path / "logs"
    with patch("src.utils.path_utils.LOGS_DIR", str(test_logs_dir)):
        logger = get_audit_logger(max_bytes=200, backup_count=2)
        log_file = get_audit_log_path()
        
        for i in range(10):
            logger.info(f"Test rotation log entry number {i} - padding long string to exceed max_bytes limit")
           # 應產生輪替備份檔
        assert os.path.exists(log_file)
        assert os.path.exists(f"{log_file}.1")

def test_save_json_file_create_and_overwrite(tmp_path):
    test_logs_dir = tmp_path / "logs"
    target_json = tmp_path / "data" / "sample.json"
    
    with patch("src.utils.path_utils.LOGS_DIR", str(test_logs_dir)):
        # 1. 首次寫入 -> CREATE
        save_json_file(str(target_json), {"version": 1}, caller_tag="test_caller:init")
        assert os.path.exists(target_json)
        with open(target_json, "r", encoding="utf-8") as f:
            assert json.load(f) == {"version": 1}
            
        log_file = get_audit_log_path()
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            assert any("action=CREATE" in line and "caller=test_caller:init" in line for line in lines)
            
        # 2. 再次寫入 -> OVERWRITE
        save_json_file(str(target_json), {"version": 2, "updated": True})
        with open(target_json, "r", encoding="utf-8") as f:
            assert json.load(f) == {"version": 2, "updated": True}
            
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            assert any("action=OVERWRITE" in line for line in lines)

def test_delete_data_file(tmp_path):
    test_logs_dir = tmp_path / "logs"
    target_file = tmp_path / "data" / "to_delete.json"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text('{"deleted": false}', encoding="utf-8")
    
    with patch("src.utils.path_utils.LOGS_DIR", str(test_logs_dir)):
        success = delete_data_file(str(target_file))
        assert success is True
        assert not os.path.exists(target_file)
        
        log_file = get_audit_log_path()
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert "action=DELETE" in content
            assert "size=0B" in content
            
        # 刪除不存在之檔案應回傳 False 且不寫入日誌
        fail_delete = delete_data_file(str(target_file))
        assert fail_delete is False
