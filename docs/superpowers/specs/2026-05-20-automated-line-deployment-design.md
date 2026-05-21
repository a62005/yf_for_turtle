# Automated LINE Bot Deployment and Configuration Design Specification

## Overview
Automate the setup process for the LINE Bot local development environment. By integrating `pyngrok`, the system will automatically open a secure tunnel and update the LINE Messaging API's Webhook URL upon startup, eliminating manual configuration steps.

## Objectives
1. **Zero-Config Startup**: Automatically start ngrok and obtain a public URL.
2. **Dynamic Webhook Sync**: Programmatically update the LINE Channel's Webhook URL to match the current ngrok tunnel.
3. **Flexible Deployment**: Seamlessly switch between local (ngrok) and cloud (static URL) environments.

## System Architecture

### 1. Environment Detection Logic
The application will prioritize configuration in the following order:
- **Cloud Mode**: If `SERVER_URL` is provided in the environment (and is not a localhost URL), use it directly. Skip ngrok setup.
- **Local Mode**: If `NGROK_AUTHTOKEN` is present in `.env`, trigger the automated setup flow.

### 2. Startup Sequence (Bootstrap)
When `bot.py` is executed:
1. **Initialize ngrok**: 
   - Load `NGROK_AUTHTOKEN`.
   - Start an HTTP tunnel on port 5000 using `pyngrok`.
   - Capture the `public_url`.
2. **Update Application State**:
   - Inject the `public_url` into the global `SERVER_URL` variable.
3. **Synchronize with LINE API**:
   - Initialize `MessagingApi` client.
   - Call `set_webhook_endpoint` with `f"{public_url}/callback"`.
   - Call `test_webhook_endpoint` to verify connectivity.
4. **Start Flask**: Launch the web server.

## Component Changes

### Configuration (`src/config.py` & `.env`)
- New Variable: `NGROK_AUTHTOKEN` (Required for local automation).

### Web Server (`bot.py`)
- Add `setup_ngrok()` helper function.
- Add `update_line_webhook(url)` helper function.
- Refactor the `if __name__ == "__main__":` block to include the bootstrap sequence.

### Dependencies (`requirements.txt`)
- Add `pyngrok`.

## Security Considerations
- **Token Protection**: `NGROK_AUTHTOKEN` must be stored in `.env` and never committed to version control (ensured by existing `.gitignore`).
- **Endpoint Exposure**: ngrok tunnels are public; ensure the LINE signature verification in `/callback` is strictly enforced (handled by `WebhookHandler`).

## Success Criteria
- Executing `python3 bot.py` successfully launches both ngrok and the Flask server.
- The LINE Bot Console reflects the new ngrok URL without manual intervention.
- Static images are correctly served via the dynamically generated URL.
