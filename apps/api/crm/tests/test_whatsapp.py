from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
from crm.generator import normalize_phone_number
from src.whatsapp import WhatsAppClient, WhatsAppError

def test_normalize_phone_number_valid():
    assert normalize_phone_number("0612345678", "+216") == "+216612345678"
    assert normalize_phone_number("+33612345678", "+216") == "+33612345678"
    assert normalize_phone_number("0033612345678", "+216") == "+33612345678"
    assert normalize_phone_number("98765432", "+216") == "+21698765432"

def test_normalize_phone_number_invalid():
    with pytest.raises(ValueError):
        normalize_phone_number("", "+216")
    with pytest.raises(ValueError):
        normalize_phone_number("123", "+216")
    with pytest.raises(ValueError):
        normalize_phone_number("+123", "+216")

@patch("src.whatsapp.requests.post")
def test_whatsapp_client_upload_media(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": "media_123"}
    mock_post.return_value = mock_response

    client = WhatsAppClient("phone_123", "token_123")
    
    with patch("src.whatsapp.Path.exists", return_value=True):
        with patch("src.whatsapp.Path.open", create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            media_id = client.upload_media(Path("dummy_path.pdf"))
        
    assert media_id == "media_123"
    assert mock_post.called

@patch("src.whatsapp.requests.post")
def test_whatsapp_client_send_document(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "messages": [{"id": "msg_123", "message_status": "accepted"}]
    }
    mock_post.return_value = mock_response

    client = WhatsAppClient("phone_123", "token_123")
    res = client.send_document(
        to_e164="+21698765432",
        media_id="media_123",
        filename="facture.pdf",
        template="note_honoraires",
        lang="fr",
        variables=["Jean", "Dupont", "note"]
    )
    assert res.message_id == "msg_123"
    assert res.status == "accepted"

@patch("src.whatsapp.requests.get")
def test_whatsapp_client_get_status(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "delivered"
    }
    mock_get.return_value = mock_response

    client = WhatsAppClient("phone_123", "token_123")
    status = client.get_status("msg_123")
    assert status == "delivered"

@patch("src.whatsapp.requests.get")
def test_whatsapp_client_get_status_error(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {
        "error": {"message": "Invalid message ID"}
    }
    mock_get.return_value = mock_response

    client = WhatsAppClient("phone_123", "token_123")
    with pytest.raises(WhatsAppError):
        client.get_status("msg_123")
