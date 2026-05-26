import os
import logging
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, PushMessageRequest, ImageMessage, TextMessage

def send_push_image(user_ids: list[str], image_url: str):
    if not user_ids:
        return
        
    token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
    if not token:
        logging.error("No LINE_CHANNEL_ACCESS_TOKEN for push message.")
        return
        
    configuration = Configuration(access_token=token)
    msg = ImageMessage(original_content_url=image_url, preview_image_url=image_url)
    
    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        for uid in user_ids:
            if uid and uid != "unknown":
                try:
                    api.push_message(PushMessageRequest(to=uid, messages=[msg]))
                    logging.info(f"Push message sent to {uid}")
                except Exception as e:
                    logging.error(f"Failed to push message to {uid}: {e}")
