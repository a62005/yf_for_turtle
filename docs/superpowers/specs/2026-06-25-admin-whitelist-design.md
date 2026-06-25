# 超級管理員與白名單權限控制設計文件

此設計文件定義了 Yahoo Fantasy NBA LINE Bot 引入超級管理員（Super Admin）與白名單（Whitelist）權限驗證機制的架構與實作規格。

## 1. 需求背景與目標

為了限制系統管理功能的存取權，且不影響一般使用者的日常查詢，我們需要實作一套輕量級的權限管理機制：
1. **超級管理員 (Super Admin)**：僅限一位，預設擁有系統最高權限（可使用所有功能，包含新增白名單成員）。
2. **白名單成員 (Whitelist)**：可使用系統設定功能（如 `#設置`）。
3. **一般使用者**：可使用除了 `#新增白名單` 及 `#設置` 以外的所有功能。
4. **權限攔截**：當使用者權限不足時，系統應「**安靜阻擋**」，不做出任何 LINE 訊息回應，以防止不必要的訊息干擾。
5. **指令直達**：權限管理相關指令（`#我的ID`、`#新增白名單`、`#設置`）應優先過濾，**不進入 LLM 意圖解析**。

---

## 2. 目錄與儲存結構

所有安全相關配置均持久化儲存於 `data/security/` 目錄下：

### 2.1 超級管理員配置
*   **路徑**：`data/security/super_admin.json`
*   **格式**：
    ```json
    {
      "super_admin": "Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    }
    ```
*   **初始化方式**：首次佈署時，由管理員手動填入其 LINE User ID。

### 2.2 白名單配置
*   **路徑**：`data/security/whitelist.json`
*   **格式**：
    ```json
    {
      "whitelist": [
        "U1111111111111111111111111111111",
        "U2222222222222222222222222222222"
      ]
    }
    ```
*   **初始化方式**：預設為空列表 `{"whitelist": []}`。後續由超級管理員透過指令動態加入。

---

## 3. 核心類別設計：`SecurityManager`

新增 `src/utils/security.py` 以實作 `SecurityManager` 類別，負責安全檔案之讀寫與驗證：

```python
class SecurityManager:
    def __init__(self, super_admin_path: str = "data/security/super_admin.json", whitelist_path: str = "data/security/whitelist.json"):
        self.super_admin_path = super_admin_path
        self.whitelist_path = whitelist_path

    def is_super_admin(self, user_id: str | None) -> bool:
        """檢查 user_id 是否為超級管理員。"""
        if not user_id:
            return False
        # 讀取 super_admin.json
        # 比對 "super_admin" 欄位
        pass

    def is_whitelisted(self, user_id: str | None) -> bool:
        """檢查 user_id 是否在白名單中，或者是否為超級管理員。"""
        if not user_id:
            return False
        if self.is_super_admin(user_id):
            return True
        # 讀取 whitelist.json
        # 檢查 user_id 是否在 "whitelist" 列表中
        pass

    def add_to_whitelist(self, user_id: str) -> bool:
        """將 user_id 加入白名單列表並寫回檔案。"""
        # 讀取 whitelist.json
        # 若 user_id 不在列表中，append 進去並保存
        # 返回是否成功寫入
        pass
```

---

## 4. 基底類別與分派器修改

### 4.1 `BaseHandler` 修改
在 `src/handlers/base_handler.py` 的 `BaseHandler` 中加入權限要求屬性（預設為 `False`）：
```python
class BaseHandler:
    def __init__(self):
        # ... 原有初始化邏輯 ...
        self.requires_super_admin: bool = False
        self.requires_whitelist: bool = False
```

### 4.2 `CommandDispatcher` 修改
修改 `src/handlers/dispatcher.py` 的 `handle` 方法：
1. 提取發送者 ID：`user_id = event.source.user_id if event.source and hasattr(event.source, 'user_id') else None`。
2. 在 `handler.can_handle(user_text)` 比對成功後，進行權限攔截：
    ```python
    if handler.requires_super_admin:
        if not security_manager.is_super_admin(user_id):
            logging.info(f"[Dispatcher] 使用者 {user_id} 嘗試執行 {handler.__class__.__name__}，因非超級管理員被安靜攔截")
            return  # 安靜退出，不回覆任何訊息

    if handler.requires_whitelist:
        if not security_manager.is_whitelisted(user_id):
            logging.info(f"[Dispatcher] 使用者 {user_id} 嘗試執行 {handler.__class__.__name__}，因非白名單成員被安靜攔截")
            return  # 安靜退出，不回覆任何訊息
    ```
3. 通過權限檢查後，正常執行 `handler.execute(event, configuration)`。

---

## 5. 新增之指令 Handlers

我們在 `src/handlers/` 下建立並註冊三個新的 Handler：

### 5.1 `IdHandler` (對應 `#我的ID`)
*   **類別名稱**：`IdHandler`
*   **權限要求**：無（`requires_super_admin = False`, `requires_whitelist = False`）
*   **意圖**：比對 `#我的ID`。此指令以 `#` 開頭，`IntentRouter` 將直接分派給 `CommandDispatcher`，不進入 LLM 意圖。
*   **行為**：
    *   回覆文字：「`您的 LINE ID 為: {user_id}`」。

### 5.2 `SuperAdminHandler` (對應 `#新增白名單 <ID>`)
*   **類別名稱**：`SuperAdminHandler`
*   **權限要求**：`requires_super_admin = True`（僅超級管理員可執行）
*   **意圖**：比對 `^#新增白名單` 的正則格式。不進入 LLM 意圖。
*   **行為**：
    *   使用正則表達式解析參數：`^#新增白名單\s+(U[a-fA-F0-9]{32})$`。
    *   若格式正確，呼叫 `SecurityManager.add_to_whitelist(target_id)`，並回覆：「`成功將 ID 加入白名單：{target_id}`」。
    *   若格式錯誤，回覆提示：「`格式錯誤，請使用：#新增白名單 <LINE_ID>`」。

### 5.3 `SettingsHandler` (對應 `#設置`)
*   **類別名稱**：`SettingsHandler`
*   **權限要求**：`requires_whitelist = True`（僅白名單成員，含超級管理員可執行）
*   **意圖**：比對 `#設置`。不進入 LLM 意圖。
*   **行為**：
    *   回覆目前系統支持的設置資訊清單（例如可查詢項目或系統屬性之文字列表）。

---

## 6. 測試策略

使用 `pytest` 撰寫單元測試以確保安全機制的正確性：
1. **SecurityManager 測試**：
   - 測試讀取正確/不存在的 `super_admin.json` 和 `whitelist.json`。
   - 測試管理員判定、白名單判定邏輯。
   - 測試重複加入白名單的防呆設計。
2. **權限攔截測試**：
   - 模擬一般使用者發送 `#新增白名單 <ID>`，驗證 `Dispatcher` 是否安靜攔截（無 `MessagingApi` 的 reply 調用）。
   - 模擬一般使用者發送 `#設置`，驗證是否安靜攔截。
   - 模擬超級管理員發送 `#新增白名單 <ID>`，驗證是否成功寫入檔案且發送成功回覆。
