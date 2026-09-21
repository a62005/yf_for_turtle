import pytest
import os
import shutil

@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data_after_suite():
    # Let all tests run
    yield
    
    # After the whole test suite completes, clean up any test data directories
    test_dirs = [
        "data/league/nba/123",
        "data/league/nba/12345",
        "data/league/nba/99999",
        "data/league/nba/default",
        "data/league/mlb/123",
        "data/league/mlb/12345",
        "data/league/mlb/99999",
        "data/league/mlb/default"
    ]
    for d in test_dirs:
        if os.path.exists(d):
            try:
                shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass

    # Clean up test audit log if created during unmocked test runs
    import logging
    audit_logger = logging.getLogger("data_audit")
    for h in list(audit_logger.handlers):
        try:
            h.close()
            audit_logger.removeHandler(h)
        except Exception:
            pass

    test_log_files = [
        "logs/data_audit.log",
        "logs/data_audit.log.1",
        "logs/data_audit.log.2",
    ]
    for f in test_log_files:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass
    if os.path.exists("logs") and not os.listdir("logs"):
        try:
            os.rmdir("logs")
        except Exception:
            pass

