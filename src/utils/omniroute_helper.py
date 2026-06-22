import os
import sqlite3
import subprocess
import tempfile
import logging

def register_gemini_key_to_omniroute():
    """
    Encrypts the GEMINI_API_KEY from project .env using omniroute's key derivation
    and inserts it into the local omniroute storage.sqlite database under provider 'gemini'.
    """
    omni_env_path = os.path.expanduser(r"~\.omniroute\.env")
    db_path = os.path.expanduser(r"~\.omniroute\storage.sqlite")
    
    # Locate project .env
    project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    project_env_path = os.path.join(project_dir, ".env")

    if not os.path.exists(omni_env_path) or not os.path.exists(db_path):
        logging.info("[SYSTEM] omniroute 設定檔或資料庫尚未初始化，跳過自動金鑰註冊。")
        return

    # 1. Read STORAGE_ENCRYPTION_KEY
    storage_key = None
    with open(omni_env_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("STORAGE_ENCRYPTION_KEY="):
                storage_key = line.split("=", 1)[1].strip()

    # 2. Read GEMINI_API_KEY
    gemini_key = None
    if os.path.exists(project_env_path):
        with open(project_env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("GEMINI_API_KEY="):
                    gemini_key = line.split("=", 1)[1].strip()

    if not storage_key or not gemini_key:
        logging.warning("[SYSTEM] 無法自動註冊 Gemini 金鑰：未找到 STORAGE_ENCRYPTION_KEY 或 GEMINI_API_KEY。")
        return

    # 3. Create Node.js script to encrypt the Gemini key
    node_code = """
const crypto = require("crypto");
const ALGORITHM = "aes-256-gcm";
const IV_LENGTH = 16;
const KEY_LENGTH = 32;
const PREFIX = "enc:v1:";
const STATIC_SALT = "omniroute-field-encryption-v1";

function encrypt(plaintext, secret) {
  if (!plaintext) return plaintext;
  const key = crypto.scryptSync(secret, STATIC_SALT, KEY_LENGTH);
  const iv = crypto.randomBytes(IV_LENGTH);
  const cipher = crypto.createCipheriv(ALGORITHM, key, iv);
  let encrypted = cipher.update(plaintext, "utf8", "hex");
  encrypted += cipher.final("hex");
  const authTag = cipher.getAuthTag().toString("hex");
  return `${PREFIX}${iv.toString("hex")}:${encrypted}:${authTag}`;
}

const plain = process.argv[2];
const secret = process.argv[3];
console.log(encrypt(plain, secret));
"""

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".js") as temp_js:
        temp_js.write(node_code)
        temp_js_path = temp_js.name

    try:
        # Run the node script
        cmd = ["node", temp_js_path, gemini_key, storage_key]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        encrypted_key = res.stdout.strip()
    except Exception as e:
        logging.error(f"[SYSTEM] 透過 Node.js 加密 Gemini 金鑰失敗: {e}")
        return
    finally:
        if os.path.exists(temp_js_path):
            try:
                os.remove(temp_js_path)
            except OSError:
                pass

    # 4. Insert into SQLite provider_connections
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        conn_id = "gemini-default"
        
        # Delete any existing gemini connection first
        cursor.execute("DELETE FROM provider_connections WHERE provider='gemini';")
        
        cursor.execute("""
            INSERT INTO provider_connections (
                id, provider, is_active, api_key, created_at, updated_at, proxy_enabled, per_key_proxy_enabled, priority
            ) VALUES (
                ?, ?, 1, ?, datetime('now'), datetime('now'), 1, 0, 1
            );
        """, (conn_id, "gemini", encrypted_key))
        
        conn.commit()
        logging.info("[SYSTEM] 成功將專案之 GEMINI_API_KEY 自動註冊至 omniroute 本地資料庫！")
        conn.close()
    except Exception as e:
        logging.error(f"[SYSTEM] 寫入 omniroute 資料庫時發生錯誤: {e}")
