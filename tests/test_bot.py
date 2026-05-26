import pytest
from unittest.mock import patch
import json

@pytest.fixture
def client():
    # Provide dummy secrets to allow bot to initialize
    import os
    os.environ["LINE_CHANNEL_SECRET"] = "dummy"
    os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "dummy"
    from bot import app
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@patch("bot.subprocess.Popen")
def test_pubsub_worker_endpoint(mock_popen, client):
    # Mock pubsub payload
    payload = {
        "message": {
            "data": "eyJ0YXJnZXRfZGF0ZSI6ICIyMDI1LTExLTE1In0=" # {"target_date": "2025-11-15"} in base64
        }
    }
    response = client.post('/pubsub-worker', json=payload)
    assert response.status_code == 200
    mock_popen.assert_called_once()
