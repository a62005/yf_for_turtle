# Automated LINE Bot Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automate the startup of ngrok and the updating of the LINE Messaging API Webhook URL to allow "one-command" deployment for local development.

**Architecture:** 
1. Integrate `pyngrok` to manage the ngrok tunnel programmatically.
2. Extend `Configuration` to include `NGROK_AUTHTOKEN`.
3. Modify `bot.py` to check for environment variables and decide whether to start ngrok and sync the webhook.
4. Implement the bootstrap sequence in `bot.py`.

**Tech Stack:** Python, Flask, pyngrok, line-bot-sdk.

---

### Task 1: Configuration and Dependencies

**Files:**
- Modify: `requirements.txt`
- Modify: `src/config.py`
- Modify: `.env.example`

- [ ] **Step 1: Add `pyngrok` dependency**
Update `requirements.txt` to include `pyngrok`.
```txt
# ... existing dependencies
pyngrok
```

- [ ] **Step 2: Update `.env.example`**
Include the new `NGROK_AUTHTOKEN` variable.
```env
# ... existing variables
NGROK_AUTHTOKEN=your_ngrok_authtoken_here
```

- [ ] **Step 3: Update `src/config.py`**
Modify `load_config()` to read `NGROK_AUTHTOKEN`.
```python
def load_config() -> dict:
    load_dotenv()
    # ... existing logic
    return {
        # ... existing keys
        "NGROK_AUTHTOKEN": os.getenv("NGROK_AUTHTOKEN"),
        "YAHOO_CLIENT_ID": os.getenv("YAHOO_CLIENT_ID"),
        "YAHOO_CLIENT_SECRET": os.getenv("YAHOO_CLIENT_SECRET"),
        "LINE_CHANNEL_SECRET": os.getenv('LINE_CHANNEL_SECRET'),
        "LINE_CHANNEL_ACCESS_TOKEN": os.getenv('LINE_CHANNEL_ACCESS_TOKEN'),
        "SERVER_URL": os.getenv('SERVER_URL')
    }
```

- [ ] **Step 4: Commit changes**
```bash
git add requirements.txt src/config.py .env.example
git commit -m "feat: add ngrok dependency and configuration"
```

---

### Task 2: Automated Bootstrap Logic in bot.py

**Files:**
- Modify: `bot.py`

- [ ] **Step 1: Add ngrok and Webhook update helpers**
Implement the logic to start ngrok and call the LINE API to update the webhook URL.
```python
# Add imports at top
from pyngrok import ngrok
from linebot.v3.messaging import SetWebhookEndpointRequest

def setup_ngrok(authtoken: str, port: int) -> str:
    """Start ngrok tunnel and return the public URL."""
    ngrok.set_auth_token(authtoken)
    tunnel = ngrok.connect(port)
    return tunnel.public_url

def update_line_webhook(configuration: Configuration, url: str):
    """Update the LINE Messaging API Webhook URL."""
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        endpoint = f"{url}/callback"
        set_webhook_request = SetWebhookEndpointRequest(endpoint=endpoint)
        try:
            line_bot_api.set_webhook_endpoint(set_webhook_request)
            # Verify connectivity
            line_bot_api.test_webhook_endpoint()
            logging.info(f"Successfully updated LINE Webhook URL to: {endpoint}")
        except Exception as e:
            logging.error(f"Failed to update LINE Webhook: {e}")
```

- [ ] **Step 2: Implement the Bootstrap Sequence**
Refactor the `if __name__ == "__main__":` block to execute the automation logic.
```python
if __name__ == "__main__":
    config = load_config()
    port = 5000
    
    # Logic to decide mode
    # If NGROK_AUTHTOKEN exists, assume local automation mode
    if config.get("NGROK_AUTHTOKEN"):
        logging.info("NGROK_AUTHTOKEN found. Starting automated setup...")
        try:
            public_url = setup_ngrok(config["NGROK_AUTHTOKEN"], port)
            # Override global SERVER_URL
            global SERVER_URL
            SERVER_URL = public_url
            logging.info(f"ngrok tunnel opened at: {public_url}")
            
            # Sync with LINE
            update_line_webhook(configuration, public_url)
        except Exception as e:
            logging.error(f"ngrok setup failed: {e}")
            logging.info("Falling back to manual SERVER_URL.")
    else:
        logging.info("No NGROK_AUTHTOKEN found. Using existing SERVER_URL.")

    app.run(host="0.0.0.0", port=port)
```

- [ ] **Step 3: Commit bot.py changes**
```bash
git add bot.py
git commit -m "feat: implement automated ngrok startup and webhook sync in bot.py"
```

---

### Task 3: Verification

- [ ] **Step 1: Test with dummy token**
Run `bot.py` with a fake token to ensure it attempts the setup and handles the error gracefully.
- [ ] **Step 2: Verify code syntax**
Run `python3 -m py_compile bot.py` to ensure no errors were introduced.
- [ ] **Step 3: Final check**
Ensure all `global SERVER_URL` references in `bot.py` are correctly updated during bootstrap.
