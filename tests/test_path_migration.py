import os
import shutil
import tempfile
import json
from src.utils.path_utils import get_league_dir, migrate_old_league_directories

def test_get_league_dir_preserves_prefix():
    # Full keys should resolve to nested sport directories
    assert "nba/18457" in get_league_dir("nba.l.18457").replace("\\", "/")
    assert "mlb/12345" in get_league_dir("mlb.l.12345").replace("\\", "/")
    assert "nba/999" in get_league_dir("999").replace("\\", "/")

def test_migrate_old_league_directories(mocker):
    temp_data_dir = tempfile.mkdtemp()
    mocker.patch("src.utils.path_utils.DATA_DIR", temp_data_dir)
    
    # Setup old numeric folder and files
    old_folder = os.path.join(temp_data_dir, "league", "18457")
    os.makedirs(old_folder, exist_ok=True)
    test_file = os.path.join(old_folder, "test.json")
    with open(test_file, "w") as f:
        f.write("{}")
        
    # Setup old dot-prefixed folder (from previous setup)
    old_dot_folder = os.path.join(temp_data_dir, "league", "nba.l.9999")
    os.makedirs(old_dot_folder, exist_ok=True)
    test_dot_file = os.path.join(old_dot_folder, "test_dot.json")
    with open(test_dot_file, "w") as f:
        f.write("{}")
        
    # Setup old mapping file
    sec_dir = os.path.join(temp_data_dir, "security")
    os.makedirs(sec_dir, exist_ok=True)
    mapping_file = os.path.join(sec_dir, "chat_league_mapping.json")
    with open(mapping_file, "w") as f:
        json.dump({"chat1": "18457"}, f)
        
    migrate_old_league_directories()
    
    # Old folders should be migrated to nba/18457 and nba/9999
    new_folder = os.path.join(temp_data_dir, "league", "nba", "18457")
    new_dot_folder = os.path.join(temp_data_dir, "league", "nba", "9999")
    
    assert os.path.exists(new_folder)
    assert os.path.exists(new_dot_folder)
    assert not os.path.exists(old_folder)
    assert not os.path.exists(old_dot_folder)
    
    # Mapping file should be updated
    with open(mapping_file, "r") as f:
        mapping = json.load(f)
    assert mapping["chat1"] == "nba.l.18457"
    
    shutil.rmtree(temp_data_dir)
