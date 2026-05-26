import pytest
from unittest.mock import patch, MagicMock, ANY
from src.utils.notify import send_push_image

@patch('src.utils.notify.MessagingApi')
@patch('src.utils.notify.ApiClient')
@patch('src.utils.notify.Configuration')
@patch('os.getenv')
def test_send_push_image(mock_getenv, mock_config, mock_api_client, mock_messaging_api):
    mock_getenv.return_value = "fake_token"
    mock_api_instance = mock_messaging_api.return_value
    
    user_ids = ["user1", "user2"]
    image_url = "http://example.com/image.png"
    
    send_push_image(user_ids, image_url)
    
    assert mock_api_instance.push_message.call_count == 2
    mock_api_instance.push_message.assert_any_call(ANY)
