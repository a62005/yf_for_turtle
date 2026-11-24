# Yahoo Fantasy League Bot

提供 Yahoo Fantasy NBA / MLB 聯賽數據抓取、視覺化戰績板與 LINE Bot 即時互動查詢的服務。

## Language

**即時對戰 (Scheduled Matchup)**:
特定玩家在當週賽程中與系統實際配對之單一對手的各項數據與比分對決（對應指令：`#對戰`）。
_Avoid_: 全聯盟比分、模擬比分

**全聯盟模擬比分 (All-Play Score Simulation)**:
將單一玩家在指定週次的累積數據，與聯盟內所有其他玩家逐一進行比項對決，依「勝場 / 平手 / 敗場」分組列出對上每一隊的總比數（勝項:敗項[:平項]）（對應指令：`#比分`）。
_Avoid_: 即時對戰、實際賽程對戰

**當週即時週數據 (Current Week Live Data)**:
當前進行中週次依據最新抓取之本地週數據檔案（`weekly/*.json`）所呈現的當下累積數據。
_Avoid_: 歷史週結算數據

**歷史週結算數據 (Historical Week Final Data)**:
已結束之過往週次中，該週最後一天（結算日）的本地週數據檔案（`weekly/*.json`）。
_Avoid_: 當週即時週數據

**聯賽玩家 (League Manager)**:
參與本 Yahoo Fantasy 聯賽、擁有並管理虛擬隊伍的真實群組成員，其名單定義於聯盟的 `team_mapping.json` 中（對應指令：`#玩家`、`#對戰`、`#比分`）。
_Avoid_: 球員、NBA 球員

**真實球員 (Real-world Player)**:
現實世界中於 NBA 出賽的職業運動員（對應指令：`#球員`）。
_Avoid_: 玩家、聯賽玩家

**球員即時比賽數據 (Live Player Boxscore)**:
透過外部即時體育 API（如 ESPN Live API）直接獲取之真實球員單場即時或最新完賽攻守數據，不受比賽是否正在進行中或 Yahoo Fantasy 本地爬蟲排程限制。
_Avoid_: 本地玩家日數據、Yahoo API 球員數據
