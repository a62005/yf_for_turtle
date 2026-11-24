# 解耦巨型 Handler 為資料倉儲 (Repository)、領域服務 (Domain Service) 與視覺渲染器 (Flex Renderer) 三層架構

Status: accepted

前期開發的 `StatsHandler`、`LocalMatchupHandler`、`LocalScoreHandler` 與 `LocalUserStatsHandler` 內部同時混雜了「本地 JSON 檔案讀取與當季週次推算」、「NBA/MLB 比項別名取值與勝負計算」以及「LINE Flex Message 畫面組裝」，甚至出現 Handler 在建構子內直接實例化其他 Handler 並跨類別呼叫 `_private` 私有方法的水平耦合。我們決定遵循單一職責原則（SRP）與依賴反轉原則（DIP），將架構拆解為三個獨立層次：
1. **資料存取倉儲層 (`LocalLeagueDataRepository`)**：統一封裝本地 `daily`/`weekly` JSON 讀取、當季開季與結束邊界判定、日期所屬週次推算與當週對戰組合配對，彻底解除 Handler 之間的私有方法依賴。
2. **領域服務層 (`FantasyStatToolkit` / `FantasyStatComparator` / `LivePlayerIdentityResolver`)**：集中管理跨模組共用的 NBA/MLB 統計欄位別名取值、百分比與小數格式化、一對一與全聯盟（All-Play）比項勝負計算，以及球員身份解析與型別契約（`@dataclass`）。
3. **獨立視覺渲染層 (`UserStatsFlexRenderer` / `MatchupFlexRenderer` / `LivePlayerFlexRenderer`)**：專職將領域數據轉換為 LINE Flex Message 結構，並統一複用 `flex_builder.py` 的公開基礎元件。

各 Handler 退居為薄控制器（Thin Controller），透過建構子依賴注入協作上述元件，同時在 Handler 上保留一行薄委派方法（Thin Delegation）以確保既有呼叫端與測試套件 100% 向下相容。
