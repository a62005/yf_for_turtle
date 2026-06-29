import os
import shutil
import tempfile
import json
from src.utils.path_utils import get_league_dir, migrate_old_league_directories

def test_get_league_dir_preserves_prefix():
    # Full keys should keep their names
    assert "nba.l.18457" in get_league_dir("nba.l.18457")
    assert "mlb.l.12345" in get_league_dir("mlb.l.12345")
    # Raw numeric keys default to nba.l. prefix
    assert "nba.l.999" in get_league_dir("999")

def test_migrate_old_league_directories(mocker):
    temp_data_dir = tempfile.mkdtemp()
    mocker.patch("src.utils.path_utils.DATA_DIR", temp_data_dir)
    
    # Setup old numeric folder and files
    old_folder = os.path.join(temp_data_dir, "league", "18457")
    os.makedirs(old_folder, exist_ok=True)
    test_file = os.path.join(old_folder, "test.json")
    with open(test_file, "w") as f:
        f.write("{}")
        
    # Setup old mapping file
    sec_dir = os.path.join(temp_data_dir, "security")
    os.makedirs(sec_dir, exist_ok=True)
    mapping_file = os.path.join(sec_dir, "chat_league_mapping.json")
    with open(mapping_file, "w") as f:
        json.dump({"chat1": "18457"}, f)
        
    migrate_old_league_directories()
    
    # Old folder should be renamed to nba.l.18457
    new_folder = os.path.join(temp_data_dir, "league", "nba.l.18457")
    assert os.path.exists(new_folder)
    assert not os.path.exists(old_folder)
    
    # Mapping file should be updated
    with open(mapping_file, "r") as f:
        mapping = json.load(f)
    assert mapping["chat1"] == "nba.l.18457"
    
    shutil.rmtree(temp_data_dir)
