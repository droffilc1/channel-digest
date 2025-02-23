import httpx
from fastapi import APIRouter, BackgroundTasks, Request, Security
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from api.db.schemas import DigestPayload

router = APIRouter()


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_auth_data(request: Request):
    """Retrieve authentication data from Swagger's Authorize header"""
    try:
        token = await oauth2_scheme(request)

        if not token:
            raise ValueError("Missing required authentication data")

        return token
    except Exception as e:
        print(f"Error getting auth data: {str(e)}")
        raise


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
                "Constructs a digest containing total messages, active users, and trending keywords.",
                "Sends the digest to a configured webhook.",
            ],
            "author": "Clifford Mapesa",
            "settings": [
                {
                    "label": "channel_id",
                    "type": "text",
                    "required": True,
                    "default": "your-channel-id",
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


async def fetch_channel_data(channel_id: str, org_id: str, request: Request):
    bearer_token = await get_auth_data(request)
    api_url = f"https://api.telex.im/api/v1/organisations/{org_id}/channels"
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(api_url, headers=headers, timeout=10)

            response.raise_for_status()
            data = response.json()

            # Extract channels array
            channels = data.get("data", {}).get("channels", [])

            # Process valid channels
            valid_channels = [ch for ch in channels if isinstance(ch, dict)]
            target_id = str(channel_id).strip()

            # Find matching channel
            found_channel = None
            for ch in valid_channels:
                ch_id = str(ch.get("channels_id", "")).strip()
                if ch_id == target_id:
                    found_channel = ch
                    break

            return found_channel

    except Exception as e:
        return None


async def generate_digest(payload: DigestPayload, request: Request):
    try:
        channel = await fetch_channel_data(
            payload.channel_id, payload.organisation_id, request
        )

        if not channel:
            message = f"Channel {payload.channel_id} not found."
            status = "error"
        else:
            channel_name = channel.get("name", "Unknown")
            total_messages = channel.get("message_count", 0)
            active_users = channel.get("user_count", 0)
            trending_keywords = channel.get("trending_keywords", [])

            message = (
                f"Channel Digest for {channel_name}:\n"
                f"- Total messages: {total_messages}\n"
                f"- Active users: {active_users}\n"
                f"- Trending keywords: {', '.join(trending_keywords) or 'N/A'}"
            )
            status = "info"

        data = {
            "message": message,
            "username": "Channel Digest",
            "event_name": "Channel Digest Report",
            "status": status,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(payload.return_url, json=data, timeout=10)
                print(f"Digest send response status: {response.status_code}")
        except Exception as e:
            print(f"\nError sending digest: {str(e)}")

    except ValueError as e:
        # Handle authentication errors
        data = {
            "message": f"Authentication error: {str(e)}",
            "username": "Channel Digest",
            "event_name": "Channel Digest Report",
            "status": "error",
        }
        async with httpx.AsyncClient() as client:
            await client.post(payload.return_url, json=data, timeout=10)


@router.post("/tick", status_code=202)
def process_digest(
    payload: DigestPayload,
    request: Request,
    background_tasks: BackgroundTasks,
    token: str = Security(oauth2_scheme),
):
    background_tasks.add_task(generate_digest, payload, request)
    return JSONResponse(content={"status": "accepted"}, status_code=202)
