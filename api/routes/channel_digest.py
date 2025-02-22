import httpx
from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from api.db.schemas import DigestPayload

router = APIRouter()


@router.get("/integration.json")
def get_integration_json(request: Request):
    base_url = str(request.base_url).rstrip("/")
    return {
        "data": {
            "date": {"created_at": "2025-02-21", "updated_at": "2025-02-21"},
            "descriptions": {
                "app_name": "Channel Digest",
                "app_description": "Generates a digest report for a channel",
                "app_url": base_url,
                "app_logo": "https://i.imgur.com/lZqvffp.png",
                "background_color": "#fff",
            },
            "is_active": True,
            "integration_category": "Data Analytics & Visualization",
            "integration_type": "interval",
            "key_features": [
                "Fetches channel details from an external API.",
                "Constructs a digest containing message count, active users, and trending keywords.",
                "Sends the digest to a configured webhook.",
            ],
            "author": "Clifford Mapesa",
            "settings": [
                {
                    "label": "channel_id",
                    "type": "text",
                    "required": True,
                    "default": "https://telex.im",
                },
                {
                    "label": "return_url",
                    "type": "text",
                    "required": True,
                    "default": "",
                },
                {
                    "label": "interval",
                    "type": "text",
                    "required": True,
                    "default": "0 * * * *",
                },
            ],
            "target_url": "",
            "tick_url": f"{base_url}/api/v1/tick",
        }
    }


async def fetch_channel_data(channel_id: str):
    api_url = "https://ping.telex.im/api/v1/channels"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(api_url, timeout=10)
            data = response.json()
            channels = data.get("data", [])
            return next((ch for ch in channels if ch["id"] == channel_id), None)
    except Exception as e:
        return None


async def generate_digest(payload: DigestPayload):
    channel = await fetch_channel_data(payload.channel_id)
    if not channel:
        message = f"Channel {payload.channel_id} not found."
        status = "error"
    else:
        message = (
            f"Channel Digest for {channel['name']}:\n"
            f"- Total messages: {channel.get('message_count', 0)}\n"
            f"- Active users: {channel.get('active_users', 0)}\n"
            f"- Trending keywords: {', '.join(channel.get('trending_keywords', [])) or 'N/A'}"
        )
        status = "info"

    data = {
        "message": message,
        "username": "Channel Digest",
        "event_name": "Channel Digest Report",
        "status": status,
    }
    async with httpx.AsyncClient() as client:
        await client.post(payload.return_url, json=data)


@router.post("/tick", status_code=202)
def process_digest(payload: DigestPayload, background_tasks: BackgroundTasks):
    background_tasks.add_task(generate_digest, payload)
    return JSONResponse(content={"status": "accepted"}, status_code=202)
