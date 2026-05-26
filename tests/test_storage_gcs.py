import pytest
from unittest.mock import patch, MagicMock
from src.storage import GCSStorage

@patch("src.storage.storage.Client")
def test_gcs_storage_save(mock_client):
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client.return_value.bucket.return_value = mock_bucket
    
    gcs_storage = GCSStorage("test_bucket")
    data = {"test": 123}
    
    path = gcs_storage.save(data, "test_id", sub_dir="weekly", overwrite=True)
    
    assert path == "weekly/test_id.json"
    mock_client.return_value.bucket.assert_called_once_with("test_bucket")
    mock_bucket.blob.assert_called_once_with("weekly/test_id.json")
    mock_blob.upload_from_string.assert_called_once()
    assert mock_blob.content_type == "application/json"
