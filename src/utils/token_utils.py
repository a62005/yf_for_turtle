from cachetools import TTLCache

# 設定一個 5 分鐘的快取，最多記錄 100 個 token
processed_tokens = TTLCache(maxsize=100, ttl=300)

def is_token_processed(token):
    if token in processed_tokens:
        return True
    processed_tokens[token] = True
    return False
