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
        "data/league/mlb/123",
        "data/league/mlb/12345",
        "data/league/mlb/99999"
    ]
    for d in test_dirs:
        if os.path.exists(d):
            try:
                shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass
