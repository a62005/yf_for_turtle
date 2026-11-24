# 以獨立類別串接 ESPN Live API 查詢球員即時數據並保留原 Yahoo API 類別

Status: accepted

由於 Yahoo Fantasy API 政策變更，原本依賴 Yahoo OAuth 與 XML 端點的 `PlayerHandler` 與 `YahooFantasyFetcher` 暫時停用；同時使用者需要查詢不受比賽進行狀態或每日爬蟲排程限制的 NBA 球員即時單場數據（Live Player Boxscore）。我們決定不修改原有的 `PlayerHandler`、`YahooFantasyFetcher`、`player_cache.py` 與 `flex_builder.py` 舊有方法，而是獨立建立職責分離的三層架構：
1. **數據擷取層 (`EspnLivePlayerFetcher`)**：封裝 ESPN 球員檢索、當日即時計分板、賽事 Boxscore 與 Gamelog 回推邏輯。
2. **視覺組裝層 (`LivePlayerFlexRenderer`)**：獨立專職將結構化球員即時數據轉換與格式化為 LINE Flex Message Bubble，不與數據擷取或 Handler 耦合。
3. **指令路由與處理層 (`LivePlayerHandler` + `live_player_cache.py`)**：處理 `#球員` 指令、串接優化後的 LLM 球員實體語意解析與本地快取。

如此既能滿足比賽進行中的毫秒級即時數據查詢並遵循單一職責原則（Separation of Concerns），未來若要復用或接回 Yahoo API，只需在 `bot.py` 切換註冊的 Handler 即可無痛還原。
