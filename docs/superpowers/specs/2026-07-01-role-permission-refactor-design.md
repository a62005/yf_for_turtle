# 聯盟級別角色管理與白名單權限控制設計文件

此設計文件定義了 Yahoo Fantasy NBA LINE Bot 權限驗證機制的重構方案。我們將原本的「全域白名單」升級為「聯盟級別角色管理」，以解決白名單成員可以跨聯盟設定他人聯盟 ID 的問題，並實作更細緻的角色權限選單。

---

## 1. 需求與目標

為了限制系統管理與綁定功能的存取權，我們將權限角色細分為以下三種：
1. **超級管理員 (Super Admin)**：
   * 僅限一位，擁有系統最高權限。
   * 可新增全域的「聯盟管理員 (Manager)」，並設定其方便識別的**識別名稱**（透過兩階段分步問答對話）。
   * 自動擁有所有聯盟的管理員與白名單權限。
2. **聯盟管理員 (Manager)**：
   * 由超級管理員指派。
   * 可以執行聊天室與聯盟 ID 的**綁定（`#設置聯盟ID`）與解綁（`#移除聯盟ID`）**。
   * 擁有該聯盟 ID 的所有權（Owner）。若某個聯盟 ID 已被 A 管理員綁定，其他管理員將無法綁定該聯盟 ID。
   * 可為其所屬的聯盟**新增與移除「白名單成員（授權成員）」**。
3. **白名單成員 (League Whitelist / 授權成員)**：
   * 由該聯盟的管理員（或超級管理員）指派，並設定其**識別名稱**（同樣透過兩階段分步問答對話）。
   * 僅可對已綁定的聊天室執行**一般設置功能**（如：調整玩家暱稱、設定獎金、選秀/開季時間）。
   * 無法看到或操作「綁定/解綁」及「成員管理（增刪）」功能。

---

## 2. 儲存結構與設定檔

所有安全相關配置均持久化儲存於 `data/security/` 目錄下：

### 2.1 超級管理員配置
* **路徑**：`data/security/super_admin.json`
* **格式**：
  ```json
  {
    "super_admin": "Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  }
  ```

### 2.2 全域管理員清單
* **路徑**：`data/security/managers.json`
* **格式**：(使用 Key-Value 對應方便識別名稱)
  ```json
  {
    "managers": {
      "U1111111111111111111111111111111": "管理員小明",
      "U2222222222222222222222222222222": "管理員小華"
    }
  }
  ```

### 2.3 聯盟角色與授權清單
* **路徑**：`data/security/league_roles.json` (取代原全域 `whitelist.json`)
* **格式**：(白名單使用 Key-Value 對應方便識別名稱)
  ```json
  {
    "nba.l.18457": {
      "manager": "U1111111111111111111111111111111",
      "whitelist": {
        "U3333333333333333333333333333333": "大雄",
        "U4444444444444444444444444444444": "胖虎"
      }
    },
    "mlb.l.62358": {
      "manager": "U2222222222222222222222222222222",
      "whitelist": {}
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

    def is_manager(self, user_id: str | None) -> bool:
        """檢查 user_id 是否為全域管理員名單成員，超級管理員預設為 True。"""

    def is_league_manager(self, user_id: str | None, league_id: str | None) -> bool:
        """檢查 user_id 是否為指定聯盟的經理管理員，超級管理員預設為 True。"""
        
    def is_league_whitelisted(self, user_id: str | None, league_id: str | None) -> bool:
        """檢查 user_id 是否在該聯盟的白名單中。
        超級管理員與該聯盟管理員自動視為在白名單中。
        """

    # --- 異動 API ---
    def add_manager(self, user_id: str, name: str) -> bool:
        """將 user_id 加入全域管理員名單，並設定其識別名稱 (限超級管理員使用)。"""

    def set_league_owner(self, league_id: str, manager_id: str) -> bool:
        """設定某個聯盟的負責人管理員。"""

    def add_to_league_whitelist(self, league_id: str, user_id: str, name: str) -> bool:
        """將使用者加入指定聯盟的白名單，並設定其識別名稱。"""

    def remove_from_league_whitelist(self, league_id: str, user_id: str) -> bool:
        """將使用者移出指定聯盟的白名單。"""
```

---

## 4. 權限攔截重構 (`BaseHandler` & `CommandDispatcher`)

### 4.1 屬性宣告
於 `src/handlers/base_handler.py` 中，將權限布林值重新定義：
*   `requires_super_admin: bool = False` (最高層級，如指派管理員)
*   `requires_manager: bool = False` (管理員層級，如綁定/解綁聯盟 ID、白名單成員維護)
*   `requires_whitelist: bool = False` (成員層級，如一般設置)

### 4.2 攔截分派邏輯 (`src/handlers/dispatcher.py`)
非授權呼叫一律**安靜阻擋**，不作出任何訊息回覆。

---

## 5. 指令 Handlers 修改與新增

### 5.1 超級管理員專屬指令 (`SuperAdminHandler`)
*   **權限**：`requires_super_admin = True`
*   **功能**：
    *   **`#新增管理員`**：觸發兩階段互動對話會話，將目標加入 `managers.json` 並綁定識別名稱。
    *   *(注：超級管理員不需要於 Bot 中執行「移除管理員」指令，若需移除可由後台手動修改 json。)*

### 5.2 聯盟綁定與解綁指令 (`SetLeagueIdHandler`)
*   **權限**：`requires_manager = True`
*   **設置聯盟 ID 流程保護**：
    *   當執行 `#設置聯盟ID <ID>` 時，系統讀取 `league_roles.json`。
    *   若該 `<ID>` 已經有管理員設定且不等於當前執行者（且當前非超級管理員），則拋出警告拒絕綁定：「`⚠️ 設置失敗，該聯盟 ID 已由其他管理員管理。`」
    *   若設定成功，系統自動在 `league_roles.json` 寫入：
        ```json
        "<ID>": {
          "manager": "{當前使用者ID}",
          "whitelist": {}
        }
        ```

### 5.3 系統設置主選單 (`SettingsHandler` / `#設置`)
*   **權限**：`requires_whitelist = True`
*   **動態 Flex Message 選單渲染**：
    *   **白名單成員**看到的選單（維持不變）：
        *   設置玩家暱稱
        *   設置獎金
        *   設置選秀/開季時間 (若為休賽季)
    *   **管理員與超級管理員**看到的選單：
        *   設置玩家暱稱
        *   設置獎金
        *   設置選秀/開季時間 (若為休賽季)
        *   `--- (分隔線) ---`
        *   **新增白名單成員** (觸發分步新增會話)
        *   **移除白名單成員** (觸發移除 Flex 選單)
        *   `--- (分隔線) ---`
        *   **移除聯盟 ID**

---

## 6. 管理與維護互動流程 (Wizard 分步會話)

為了降低輸入錯誤，新增管理員與新增成員皆改為**分步（兩階段）問答對話**，每步限時 60 秒：

### 6.1 超級管理員新增管理員 (Step-by-Step Flow)
1. **觸發指令**：超級管理員輸入 **`#新增管理員`**。
2. **第一步：詢問 ID**：
   * 系統建立 Session：`add_manager`，設定 `step: 1`。
   * 回覆：「`請在 60 秒內輸入欲新增的管理員 LINE ID（例如：U123456...），或輸入 # 取消：`」。
3. **第一步輸入接收**：
   * 若輸入 `#`，取消會話。
   * 驗證是否符合 LINE ID 格式（`U[a-fA-F0-9]{32}`）。若不符，提示重新輸入。
   * 若正確，Session 儲存 `target_id`，並變更為 `step: 2`。
   * **第二步：詢問識別名稱**：
     * 回覆：「`請在 60 秒內輸入該管理員的方便識別名稱（例如：小明），或輸入 # 取消：`」。
4. **第二步輸入接收**：
   * 若輸入 `#`，取消會話。
   * 取得文字作為 `display_name`。
   * 呼叫 `security_manager.add_manager(target_id, display_name)`。
   * 回覆：「`✅ 成功新增全域管理員：{display_name} ({target_id})`」。
   * 清除會話。

### 6.2 聯盟管理員新增白名單成員 (Step-by-Step Flow)
1. **觸發指令**：聯盟管理員點選按鈕傳送 **`#新增白名單成員`**。
2. **第一步：詢問 ID**：
   * 系統建立 Session：`add_whitelist_member`，設定 `step: 1`。
   * 回覆：「`請在 60 秒內輸入欲新增的成員 LINE ID（例如：U123456...），或輸入 # 取消：`」。
3. **第一步輸入接收**：
   * 若輸入 `#`，取消會話。
   * 驗證是否符合 LINE ID 格式（`U[a-fA-F0-9]{32}`）。若不符，提示重新輸入。
   * 若正確，Session 儲存 `target_id`，並變更為 `step: 2`。
   * **第二步：詢問識別名稱**：
     * 回覆：「`請在 60 秒內輸入該成員的方便識別名稱（例如：大雄），或輸入 # 取消：`」。
4. **第二步輸入接收**：
   * 若輸入 `#`，取消會話。
   * 取得文字作為 `display_name`。
   * 呼叫 `security_manager.add_to_league_whitelist(league_id, target_id, display_name)`。
   * 回覆：「`✅ 成功將成員 {display_name} ({target_id}) 加入此聯盟的白名單成員。`」。
   * 清除會話。

### 6.3 聯盟管理員移除白名單成員 (Flex 點擊直達)
1. **觸發指令**：用戶（限管理員以上）點選按鈕傳送 **`#移除白名單成員`**。
2. **Flex 列表渲染**：系統讀取該聯盟的 `whitelist` 對應表，生成一個 Flex Message 列表：
   * 標題：「移除白名單成員」
   * 內容顯示所有成員名稱與 ID。
   * 每個成員旁有一個「移除」按鈕，其 Action 綁定傳送訊息指令：**`#確切移除白名單 <LINE_ID>`**。
3. **確切移除執行**：
   * 當點擊按鈕傳送 `#確切移除白名單 <LINE_ID>` 時，此指令需要 `requires_manager = True`。
   * 系統取得參數 `<LINE_ID>`，讀取該名單之自定義名稱後：
     * 呼叫 `security_manager.remove_from_league_whitelist(league_id, target_id)`。
     * 回覆：「`✅ 成功將成員 {display_name} 移出此聯盟的白名單。`」。

---

## 7. 測試策略與驗證

1. **`SecurityManager` 測試**：
   * 驗證 Key-Value 結構寫入與讀取的正確性。
2. **分步互動對話測試**：
   * 驗證第一步輸入合法/非法 LINE ID，系統正確切換 Step 與提示。
   * 驗證第二步輸入名稱後，資訊被正確關聯儲存。
   * 驗證兩者（管理員/成員）皆能遵循獨立的會話步驟正常完成。
3. **移除白名單測試**：
   * 驗證傳送 `#確切移除白名單 <LINE_ID>` 能順利移出並讀取自定義名稱。
