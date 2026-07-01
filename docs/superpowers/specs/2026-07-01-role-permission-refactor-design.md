# 聯盟級別角色管理與白名單權限控制設計文件

此設計文件定義了 Yahoo Fantasy NBA LINE Bot 權限驗證機制的重構方案。我們將原本的「全域白名單」升級為「聯盟級別角色管理」，以解決白名單成員可以跨聯盟設定他人聯盟 ID 的問題，並實作更細緻的角色權限選單。

---

## 1. 需求與目標

為了限制系統管理與綁定功能的存取權，我們將權限角色細分為以下三種：
1. **超級管理員 (Super Admin)**：
   * 僅限一位，擁有系統最高權限。
   * 可新增或移除全域的「聯盟管理員 (Manager)」。
   * 自動擁有所有聯盟的管理員與白名單權限。
2. **聯盟管理員 (Manager)**：
   * 由超級管理員指派。
   * 可以執行聊天室與聯盟 ID 的**綁定（`#設置聯盟ID`）與解綁（`#移除聯盟ID`）**。
   * 擁有該聯盟 ID 的所有權（Owner）。若某個聯盟 ID 已被 A 管理員綁定，其他管理員將無法綁定該聯盟 ID。
   * 可為其所屬的聯盟**新增或移除「白名單成員（授權成員）」**。
3. **白名單成員 (League Whitelist / 授權成員)**：
   * 由該聯盟的管理員（或超級管理員）指派。
   * 僅可對已綁定的聊天室執行**一般設置功能**（如：調整玩家暱稱、設定獎金、選秀/開季時間）。
   * 無法看到或操作「綁定/解綁」及「成員增刪」功能。

---

## 2. 儲存結構與設定檔

所有安全相關配置均持久化儲存於 `data/security/` 目錄下：

### 2.1 超級管理員配置
* **路徑**：`data/security/super_admin.json` (維持不變)
* **格式**：
  ```json
  {
    "super_admin": "Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  }
  ```

### 2.2 全域管理員清單
* **路徑**：`data/security/managers.json` (新增)
* **格式**：
  ```json
  {
    "managers": [
      "U1111111111111111111111111111111",
      "U2222222222222222222222222222222"
    ]
  }
  ```

### 2.3 聯盟角色與授權清單
* **路徑**：`data/security/league_roles.json` (新增，取代原全域 `whitelist.json`)
* **格式**：
  ```json
  {
    "nba.l.18457": {
      "manager": "U1111111111111111111111111111111",
      "whitelist": [
        "U3333333333333333333333333333333",
        "U4444444444444444444444444444444"
      ]
    },
    "mlb.l.62358": {
      "manager": "U2222222222222222222222222222222",
      "whitelist": []
    }
  }
  ```

### 2.4 聊天室與聯盟對應關係
* **路徑**：`data/security/chat_league_mapping.json` (維持不變)
* **格式**：
  ```json
  {
    "Ce689309ed07e6bcc4bf73264dc81fdfb": "mlb.l.62358"
  }
  ```
  *(注：在此 Mapping 中，一個 `chat_id` 鍵只能對應一個 `league_id` 值，自然符合「一個群組/聊天室只能綁定一個聯盟ID」之限制。)*

---

## 3. 核心類別設計：`SecurityManager` 升級

重構 `src/utils/security.py` 以擴充層級權限判定：

```python
class SecurityManager:
    def __init__(self, super_admin_path: str = "data/security/super_admin.json",
                 managers_path: str = "data/security/managers.json",
                 league_roles_path: str = "data/security/league_roles.json"):
        self.super_admin_path = super_admin_path
        self.managers_path = managers_path
        self.league_roles_path = league_roles_path

    # --- 查詢 API ---
    def is_super_admin(self, user_id: str | None) -> bool:
        """檢查 user_id 是否為超級管理員。"""
        # 讀取 super_admin.json ...

    def is_manager(self, user_id: str | None) -> bool:
        """檢查 user_id 是否為全域管理員名單成員，超級管理員預設為 True。"""
        if not user_id:
            return False
        if self.is_super_admin(user_id):
            return True
        # 讀取 managers.json ...

    def is_league_manager(self, user_id: str | None, league_id: str | None) -> bool:
        """檢查 user_id 是否為指定聯盟的經理管理員，超級管理員預設為 True。"""
        if not user_id:
            return False
        if self.is_super_admin(user_id):
            return True
        if not league_id:
            return False
        # 讀取 league_roles.json，比對該 league_id 的 "manager" 是否等於 user_id
        
    def is_league_whitelisted(self, user_id: str | None, league_id: str | None) -> bool:
        """檢查 user_id 是否在該聯盟的白名單中。
        超級管理員與該聯盟管理員自動視為在白名單中。
        """
        if not user_id:
            return False
        if self.is_super_admin(user_id):
            return True
        if not league_id:
            return False
        if self.is_league_manager(user_id, league_id):
            return True
        # 讀取 league_roles.json，檢查 user_id 是否在該 league_id 的 "whitelist" 列表中

    # --- 異動 API ---
    def add_manager(self, user_id: str) -> bool:
        """將 user_id 加入全域管理員名單 (限超級管理員使用)。"""
        
    def remove_manager(self, user_id: str) -> bool:
        """將 user_id 移出全域管理員名單 (限超級管理員使用)。"""

    def set_league_owner(self, league_id: str, manager_id: str) -> bool:
        """設定某個聯盟的負責人管理員。"""

    def add_to_league_whitelist(self, league_id: str, user_id: str) -> bool:
        """將使用者加入指定聯盟的白名單成員中。"""

    def remove_from_league_whitelist(self, league_id: str, user_id: str) -> bool:
        """將使用者移出指定聯盟的白名單成員。"""
```

---

## 4. 權限攔截重構 (`BaseHandler` & `CommandDispatcher`)

### 4.1 屬性宣告
於 `src/handlers/base_handler.py` 中，將權限布林值重新定義：
*   `requires_super_admin: bool = False` (最高層級，如增刪管理員)
*   `requires_manager: bool = False` (管理員層級，如綁定/解綁聯盟 ID)
*   `requires_whitelist: bool = False` (成員層級，如一般設置)

### 4.2 攔截分派邏輯 (`src/handlers/dispatcher.py`)
在分派器處理指令時，權限過濾規則如下：
1. **取得對話上下文聯賽資訊**：藉由當前群組 ID 取得對應綁定的 `league_id`（可能為 `None`）。
2. **超級管理員攔截**：若 `requires_super_admin` 為 `True`，則必須 `is_super_admin(user_id)` 為真。
3. **管理員攔截**：若 `requires_manager` 為 `True`：
   * 若當前聊天室已綁定 `league_id`，則必須滿足 `is_league_manager(user_id, league_id)`。
   * 若當前聊天室未綁定（即將進行綁定），則呼叫者必須具備全域管理員身份：`is_manager(user_id)`。
4. **白名單攔截**：若 `requires_whitelist` 為 `True`：
   * 必須滿足 `is_league_whitelisted(user_id, league_id)`。
   * 若無綁定 `league_id`，則僅放行管理員/超級管理員進行基礎初始面板的操作。

非授權呼叫一律**安靜阻擋**，不作出任何訊息回覆。

---

## 5. 指令 Handlers 修改與新增

### 5.1 超級管理員專屬指令 (`SuperAdminHandler`)
*   **權限**：`requires_super_admin = True`
*   **功能**：廢除舊有 `#新增白名單`，重構為支援管理員角色管理：
    *   **`#新增管理員 <LINE_ID>`**：將目標加入 `managers.json`。
    *   **`#移除管理員 <LINE_ID>`**：自 `managers.json` 中移除目標。

### 5.2 聯盟綁定與解綁指令 (`SetLeagueIdHandler`)
*   **權限**：`requires_manager = True`
*   **設置聯盟 ID 流程保護**：
    *   當執行 `#設置聯盟ID <ID>` 時，系統讀取 `league_roles.json`。
    *   若該 `<ID>` 已經有管理員設定且不等於當前執行者（且當前非超級管理員），則拋出警告拒絕綁定：「`⚠️ 設置失敗，該聯盟 ID 已由其他管理員管理。`」
    *   若設定成功，系統自動在 `league_roles.json` 寫入：
        ```json
        "<ID>": {
          "manager": "{當前使用者ID}",
          "whitelist": []
        }
        ```

### 5.3 系統設置主選單 (`SettingsHandler` / `#設置`)
*   **權限**：`requires_whitelist = True`
*   **動態 Flex Message 選單渲染**：
    *   取得當前聊天室的 `league_id` 以及執行者的 `user_id`。
    *   **白名單成員**看到的選單（維持不變，不包含敏感項目）：
        *   設置玩家暱稱
        *   設置獎金
        *   設置選秀/開季時間 (若為休賽季)
    *   **管理員與超級管理員**看到的選單（額外附加管理選項與分隔線）：
        *   設置玩家暱稱
        *   設置獎金
        *   設置選秀/開季時間 (若為休賽季)
        *   `--- (分隔線) ---`
        *   **新增白名單成員** (觸發會話流)
        *   **移除白名單成員** (觸發會話流)
        *   `--- (分隔線) ---`
        *   **移除聯盟 ID**

---

## 6. 成員管理互動會話 (Session Flow)

在 `#設置` 面板中，點選新增/移除白名單成員後，會進入類似綁定 ID 的 60 秒對話會話：

### 6.1 新增白名單成員
1. **觸發指令**：用戶（限管理員以上）點選按鈕傳送 **`#新增白名單成員`**。
2. **會話建立**：`session_manager` 設定狀態為 `add_whitelist_member`。
3. **提示訊息**：回覆：「`請在 60 秒內輸入要新增的成員 LINE ID（例如 U123456...），或輸入 # 取消：`」。
4. **意圖攔截**：`IntentRouter` 攔截後續文字輸入：
   * 若輸入 `#`，清除 Session 並取消。
   * 若輸入符合 LINE ID 格式（`U[a-fA-F0-9]{32}`）：
     * 呼叫 `security_manager.add_to_league_whitelist(league_id, target_id)`。
     * 回覆：「`✅ 成功將使用者 {target_id} 加入此聯盟的白名單成員。`」。
     * 清除會話。
   * 若格式不符，提示錯誤並請重新輸入。

### 6.2 移除白名單成員
1. **觸發指令**：用戶（限管理員以上）點選按鈕傳送 **`#移除白名單成員`**。
2. **會話建立**：`session_manager` 設定狀態為 `remove_whitelist_member`。
3. **提示訊息**：回覆：「`請在 60 秒內輸入要移除的成員 LINE ID（例如 U123456...），或輸入 # 取消：`」。
4. **意圖攔截**：`IntentRouter` 攔截後續文字輸入：
   * 若輸入 `#`，清除 Session 並取消。
   * 若輸入符合 LINE ID 格式，且該用戶在當前聯盟白名單中：
     * 呼叫 `security_manager.remove_from_league_whitelist(league_id, target_id)`。
     * 回覆：「`✅ 成功將使用者 {target_id} 移出此聯盟的白名單。`」。
     * 清除會話。

---

## 7. 測試策略與驗證

1. **`SecurityManager` 升級測試**：
   * 模擬載入/更新 `managers.json` 與 `league_roles.json`。
   * 驗證 `is_league_manager` 與 `is_league_whitelisted` 的邏輯鏈與自動繼承。
2. **分派器權限攔截測試**：
   * 驗證非管理員調用 `#設置聯盟ID` 時被安靜攔截。
   * 驗證非該聯盟管理員調用 `#移除聯盟ID` 時被安靜攔截。
   * 驗證非本聯盟白名單成員發送 `#設置` 時被安靜攔截。
3. **選單渲染與互動測試**：
   * 驗證白名單成員與管理員取得的 `#設置` Flex Message 結構與按鈕確實分流。
   * 測試新增/移除白名單成員的互動會話（輸入合法 ID、非法 ID、取消）之狀態變更與持久化寫入。
