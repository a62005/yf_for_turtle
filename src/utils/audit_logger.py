import os
import inspect
import logging
from logging.handlers import RotatingFileHandler
from src.utils.path_utils import get_logs_dir, DATA_DIR, BASE_DIR

AUDIT_LOGGER_NAME = "data_audit"

def get_audit_log_path() -> str:
    """獲取稽核日誌檔案完整路徑。"""
    logs_dir = get_logs_dir()
    return os.path.join(logs_dir, "data_audit.log")

def get_audit_logger(max_bytes: int = 5 * 1024 * 1024, backup_count: int = 5) -> logging.Logger:
    """
    獲取或初始化專屬的 DataAuditLogger。
    使用 RotatingFileHandler 進行檔案輪替，防止日誌無限膨脹。
    """
    logger = logging.getLogger(AUDIT_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # 避免重複傳遞至 root logger
    
    log_file = get_audit_log_path()
    logs_dir = os.path.dirname(log_file)
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir, exist_ok=True)
        
    handler_exists = False
    for h in logger.handlers:
        if isinstance(h, RotatingFileHandler) and os.path.abspath(h.baseFilename) == os.path.abspath(log_file):
            handler_exists = True
            break
            
    if not handler_exists:
        for h in list(logger.handlers):
            logger.removeHandler(h)
            try:
                h.close()
            except Exception:
                pass
                
        handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8"
        )
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] [DATA_AUDIT] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger

def _normalize_data_path(filepath: str) -> str:
    """將檔案路徑轉為相對於 data/ 目錄或專案根目錄的簡明相對路徑。"""
    abs_filepath = os.path.abspath(filepath)
    abs_data_dir = os.path.abspath(DATA_DIR)
    abs_base_dir = os.path.abspath(BASE_DIR)
    
    if abs_filepath.startswith(abs_data_dir):
        rel_path = os.path.relpath(abs_filepath, abs_data_dir)
    elif abs_filepath.startswith(abs_base_dir):
        rel_path = os.path.relpath(abs_filepath, abs_base_dir)
    else:
        rel_path = filepath
    return rel_path.replace("\\", "/")

def _detect_caller() -> str:
    """自動偵測發起資料異動的呼叫端檔名與函式名。"""
    try:
        stack = inspect.stack()
        for frame_info in stack[2:]:
            filename = os.path.basename(frame_info.filename)
            if filename != "audit_logger.py":
                return f"{filename}:{frame_info.function}"
    except Exception:
        pass
    return "unknown"

def record_data_change(action: str, filepath: str, size: int = 0, caller_tag: str = None) -> None:
    """
    核心記錄函式：寫入一筆資料稽核日誌。
    Fail-Safe：即使記錄失敗，也不中斷業務流程。
    """
    try:
        caller = caller_tag or _detect_caller()
        rel_path = _normalize_data_path(filepath)
        size_str = f"{size}B"
        
        logger = get_audit_logger()
        logger.info(f"action={action} path={rel_path} size={size_str} caller={caller}")
    except Exception as e:
        logging.warning(f"[DataAuditLogger Warning] Failed to record data audit log: {e}")
