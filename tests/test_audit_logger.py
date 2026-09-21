import os
import pytest
from unittest.mock import patch
from src.utils.audit_logger import get_audit_logger, record_data_change, get_audit_log_path

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
            
        assert os.path.exists(log_file)
        assert os.path.exists(f"{log_file}.1")
