import pytest
from src.handlers.stats_handler import StatsHandler
from src.handlers.matchup_handler import MatchupHandler
from src.handlers.player_handler import PlayerHandler
from src.handlers.misc_handler import MiscHandler

def test_handler_instruction_descs():
    assert len(StatsHandler().instruction_desc.strip()) > 0
    assert len(MatchupHandler().instruction_desc.strip()) > 0
    assert len(PlayerHandler().instruction_desc.strip()) > 0
    assert len(MiscHandler().instruction_desc.strip()) > 0
