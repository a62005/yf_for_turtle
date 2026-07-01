# 移除聯盟時保留 Yahoo 授權優化實作計劃 (Preserve Yahoo Auth on Remove Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 解除群組與聯盟ID綁定時，當該聯盟不再有任何綁定的群組時，不刪除 `.yahoofantasy` 授權憑證，其餘戰績與暫存檔案一律清除。

**Architecture:** 修改 `SetLeagueIdHandler` 中確認解綁邏輯，將原本的 `shutil.rmtree` 刪除整聯賽目錄，修改為遍歷目錄，保留檔名為 `.yahoofantasy` 或包含 `.yahoo` 的檔案與目錄，其餘則移除。

**Tech Stack:** Python 3.14, unittest.mock, pytest

---

### Task 1: 新增與更新 SetLeagueIdHandler 單元測試

**Files:**
- Modify: `tests/handlers/test_settings_and_setup.py:299-347`

- [ ] **Step 1: 撰寫預期失敗的新增與更新測試**

修改 `tests/handlers/test_settings_and_setup.py` 中 `test_set_league_id_handler_remove_success_and_delete_directory` 測試，並新增 `test_set_league_id_handler_remove_success_preserves_auth`：

```python
def test_set_league_id_handler_remove_success_and_delete_directory():
    from src.config import current_chat_id
    import json
    
    handler = SetLeagueIdHandler()
    handler.reply_text = MagicMock()
    event = MagicMock()
    event.message.text = "#確定移除聯盟ID"
    config = MagicMock()
    
    written_data = {}
    def mock_mapping_io(path, mode="r", *args, **kwargs):
        import io
        class MockFile(io.StringIO):
            def __enter__(self): return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                nonlocal written_data
                val = self.getvalue()
                if val: written_data = json.loads(val)
            def close(self):
                nonlocal written_data
                val = self.getvalue()
                if val: written_data = json.loads(val)
                super().close()
                
        if "chat_league_mapping.json" in str(path).replace("\\", "/"):
            if "r" in mode:
                # 只有 group_1 綁定 nba.l.22222
                return MockFile('{"group_1": "nba.l.22222"}')
            return MockFile()
        return open(path, mode, *args, **kwargs)

    token = current_chat_id.set("group_1")
    try:
        with patch("src.handlers.set_league_id_handler.open", side_effect=mock_mapping_io), \
             patch("src.handlers.set_league_id_handler.os.path.exists", return_value=True), \
             patch("src.handlers.set_league_id_handler.get_league_dir", return_value="mock_dir/nba/22222"), \
             patch("os.listdir", return_value=["metadata.json"]) as mock_listdir, \
             patch("os.path.isdir", return_value=False), \
             patch("os.remove") as mock_remove, \
             patch("shutil.rmtree") as mock_rmtree:
             
            handler.execute(event, config)
            
            assert "group_1" not in written_data
            mock_remove.assert_called_once_with("mock_dir/nba/22222\\metadata.json")
            mock_rmtree.assert_not_called()
            handler.reply_text.assert_called_once_with(event, config, "✅ 已成功解除此群組的聯盟綁定。")
    finally:
        current_chat_id.reset(token)

def test_set_league_id_handler_remove_success_preserves_auth():
    from src.config import current_chat_id
    import json
    
    handler = SetLeagueIdHandler()
    handler.reply_text = MagicMock()
    event = MagicMock()
    event.message.text = "#確定移除聯盟ID"
    config = MagicMock()
    
    written_data = {}
    def mock_mapping_io(path, mode="r", *args, **kwargs):
        import io
        class MockFile(io.StringIO):
            def __enter__(self): return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                nonlocal written_data
                val = self.getvalue()
                if val: written_data = json.loads(val)
            def close(self):
                nonlocal written_data
                val = self.getvalue()
                if val: written_data = json.loads(val)
                super().close()
                
        if "chat_league_mapping.json" in str(path).replace("\\", "/"):
            if "r" in mode:
                # 只有 group_1 綁定 nba.l.22222
                return MockFile('{"group_1": "nba.l.22222"}')
            return MockFile()
        return open(path, mode, *args, **kwargs)

    token = current_chat_id.set("group_1")
    try:
        with patch("src.handlers.set_league_id_handler.open", side_effect=mock_mapping_io), \
             patch("src.handlers.set_league_id_handler.os.path.exists", return_value=True), \
             patch("src.handlers.set_league_id_handler.get_league_dir", return_value="mock_dir/nba/22222"), \
             patch("os.listdir", return_value=[".yahoofantasy", "metadata.json", "daily", "some_oauth.json.tmp"]) as mock_listdir, \
             patch("os.path.isdir", side_effect=lambda p: "daily" in p) as mock_isdir, \
             patch("os.remove") as mock_remove, \
             patch("shutil.rmtree") as mock_rmtree:
             
            handler.execute(event, config)
            
            assert "group_1" not in written_data
            mock_listdir.assert_called_once_with("mock_dir/nba/22222")
            mock_remove.assert_any_call("mock_dir/nba/22222\\metadata.json")
            
            # 確保 .yahoofantasy 與包含 .yahoo 的項目皆未被刪除
            for call_args in mock_remove.call_args_list:
                assert ".yahoofantasy" not in call_args[0][0]
                assert "some_oauth.json.tmp" not in call_args[0][0]
            for call_args in mock_rmtree.call_args_list:
                assert ".yahoofantasy" not in call_args[0][0]
                
            mock_rmtree.assert_any_call("mock_dir/nba/22222\\daily")
            handler.reply_text.assert_called_once_with(event, config, "✅ 已成功解除此群組的聯盟綁定。")
    finally:
        current_chat_id.reset(token)
```

- [ ] **Step 2: 執行測試並驗證失敗**

執行測試命令：
`.venv\Scripts\python -m pytest tests/handlers/test_settings_and_setup.py::test_set_league_id_handler_remove_success_and_delete_directory -v`
預期輸出：測試 FAIL (因為原本程式會直接呼叫 `shutil.rmtree` 刪除整個目錄，與新增的 mock_remove 及 listdir 斷言不符)。

---

### Task 2: 修改 SetLeagueIdHandler 實現過濾清理

**Files:**
- Modify: `src/handlers/set_league_id_handler.py:80-88`

- [ ] **Step 1: 實作過濾清理邏輯**

修改 [src/handlers/set_league_id_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/set_league_id_handler.py)，將原本直接對孤立聯賽目錄調用 `shutil.rmtree` 改為精確過濾清理：

```python
            # 3. 若為孤立聯賽，刪除整個資料夾 (但保留授權快取憑證)
            if not has_others:
                league_dir = get_league_dir(removed_league_id)
                if os.path.exists(league_dir):
                    try:
                        for item in os.listdir(league_dir):
                            item_path = os.path.join(league_dir, item)
                            # 保留 .yahoofantasy 授權憑證或包含 .yahoo 的授權設定檔
                            if item == ".yahoofantasy" or ".yahoo" in item:
                                logging.info(f"[SetLeagueIdHandler] 保留授權憑證: {item_path}")
                                continue
                            
                            if os.path.isdir(item_path):
                                shutil.rmtree(item_path)
                            else:
                                os.remove(item_path)
                        logging.info(f"[SetLeagueIdHandler] 已成功清理孤立聯賽目錄 (保留授權憑證): {league_dir}")
                    except Exception as delete_error:
                        logging.error(f"[SetLeagueIdHandler] 清理聯賽目錄 {league_dir} 失敗: {delete_error}")
```

- [ ] **Step 2: 執行單元測試並驗證成功**

執行測試命令：
`.venv\Scripts\python -m pytest tests/handlers/test_settings_and_setup.py -v`
預期輸出：PASS。

- [ ] **Step 3: 執行全體專案測試**

執行：
`.venv\Scripts\python -m pytest`
確保所有 259 個單元測試均無 regression。

- [ ] **Step 4: Commit 提交變更**

```bash
git add src/handlers/set_league_id_handler.py tests/handlers/test_settings_and_setup.py
git commit -m "feat: preserve .yahoofantasy credentials when removing last league ID binding"
```
