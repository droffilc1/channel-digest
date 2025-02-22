import pytest
from tests import client
from unittest.mock import patch


@pytest.mark.asyncio
async def test_get_integration_json():
    response = client.get("/integration.json")
    assert response.status_code == 200
    res = response.json()
    data = res.get("data")
    assert "descriptions" in data
    assert len(data.get("settings")) == 3
    assert data.get("tick_url").endswith("/tick")


@pytest.mark.asyncio
async def test_tick_endpoint_success():
    payload = {
        "channel_id": "test_channel",
        "return_url": "http://test_url",
        "settings": [
            {"label": "channel_id", "type": "text", "required": True, "default": ""},
        ],
    }

    # Mock channel data to return
    mock_channel = {
        "id": "test_channel",
        "name": "Test Channel",
        "message_count": 100,
        "active_users": 10,
        "trending_keywords": ["test", "keywords"],
    }

    # Mock both the channel fetch and the post request
    with (
        patch("api.routes.channel_digest.fetch_channel_data") as mock_fetch,
        patch("httpx.AsyncClient.post") as mock_post,
    ):
        # Setup mock response for channel fetch
        mock_fetch.return_value = mock_channel

        response = client.post("/tick", json=payload)
        assert response.status_code == 202
        assert response.json() == {"status": "accepted"}

        mock_post.assert_awaited_once()
        mock_post.assert_awaited_with(
            "http://test_url",
            json={
                "message": "Channel Digest for Test Channel:\n- Total messages: 100\n- Active users: 10\n- Trending keywords: test, keywords",
                "username": "Channel Digest",
                "event_name": "Channel Digest Report",
                "status": "info",
            },
        )


@pytest.mark.asyncio
async def test_tick_endpoint_channel_not_found():
    payload = {
        "channel_id": "test_channel",
        "return_url": "http://test_url",
        "settings": [
            {"label": "channel_id", "type": "text", "required": True, "default": ""},
        ],
    }

    # Mock both the channel fetch and the post request
    with (
        patch("api.routes.channel_digest.fetch_channel_data") as mock_fetch,
        patch("httpx.AsyncClient.post") as mock_post,
    ):
        # Setup mock response for channel fetch to return None
        mock_fetch.return_value = None

        response = client.post("/tick", json=payload)
        assert response.status_code == 202
        assert response.json() == {"status": "accepted"}

        mock_post.assert_awaited_once()
        mock_post.assert_awaited_with(
            "http://test_url",
            json={
                "message": "Channel test_channel not found.",
                "username": "Channel Digest",
                "event_name": "Channel Digest Report",
                "status": "error",
            },
        )
