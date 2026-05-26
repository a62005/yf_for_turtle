import pytest
from src.utils.token_utils import is_token_processed, processed_tokens

def test_is_token_processed_new_token():
    # Setup: ensure cache is clear
    processed_tokens.clear()
    
    token = "new_unique_token_123"
    
    # Action & Assert: first time should return False
    assert is_token_processed(token) is False
    
    # Action & Assert: second time should return True
    assert is_token_processed(token) is True
    
def test_is_token_processed_multiple_tokens():
    processed_tokens.clear()
    
    token1 = "token_A"
    token2 = "token_B"
    
    assert is_token_processed(token1) is False
    assert is_token_processed(token2) is False
    
    assert is_token_processed(token1) is True
    assert is_token_processed(token2) is True
