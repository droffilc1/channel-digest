import httpx
from fastapi import APIRouter, BackgroundTasks, Request, Security
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer

from api.db.schemas import DigestPayload

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


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
                    "default": "",
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


async def fetch_channel_data(channel_id: str, org_id: str, token: str):
    api_url = f"https://api.telex.im/api/v1/organisations/{org_id}/channels"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    params = {"limit": 100}  # Increase the limit per page

    try:
        async with httpx.AsyncClient() as client:
            direct_url = f"{api_url}/{channel_id}"
            try:
                response = await client.get(direct_url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    print(f"Channel Data: {data}")
                    channel = data.get("data", {}).get("channel")
                    if channel:
                        print(f"Found channel directly: {channel}")
                        return channel
            except Exception as e:
                print(f"Direct channel fetch failed: {e}")

            # If direct fetch fails, try paginated list
            page = 1
            while True:
                params["page"] = page
                response = await client.get(
                    api_url, headers=headers, params=params, timeout=10
                )
                response.raise_for_status()
                data = response.json()

                channels = data.get("data", {}).get("channels", [])
                if not channels:
                    break

                channel = next(
                    (ch for ch in channels if ch.get("channels_id") == channel_id), None
                )

                if channel:
                    print(f"Found channel on page {page}: {channel}")
                    return channel

                page += 1

            print(f"Channel not found after checking {page - 1} pages")
            return None

    except Exception as e:
        print(f"Error fetching channel data: {e}")
        return None


async def generate_digest(payload: DigestPayload, token: str):
    try:
        channel = await fetch_channel_data(
            payload.channel_id, payload.organisation_id, token
        )

        if channel is None:
            message = f"Channel {payload.channel_id} not found."
            status = "error"
        else:
            channel_name = channel.get("name", "Unknown")
            message_count = channel.get("message_count", 0)
            user_count = channel.get("user_count", 0)

            message = (
                f"📊 Channel Digest Report for #{channel_name}\n\n"
                f"📨 Messages: {message_count}\n"
                f"👥 Active Users: {user_count}\n"
                f"🔍 Activity Status: {'Quiet - No messages yet' if message_count == 0 else 'Active'}"
            )
            status = "info"

        data = {
            "event_name": "Channel Digest Report",
            "message": message,
            "status": status,
            "username": "Channel Digest",
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    payload.return_url,
                    json=data,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    timeout=10,
                )
                response.raise_for_status()
            except httpx.HTTPError as http_err:
                raise http_err
            except Exception as post_err:
                raise post_err

    except Exception as e:
        error_data = {
            "event_name": "Channel Digest Report",
            "message": f"Error generating digest: {str(e)}",
            "status": "error",
            "username": "Channel Digest",
        }
        async with httpx.AsyncClient() as client:
            try:
                error_response = await client.post(
                    payload.return_url,
                    json=error_data,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    timeout=10,
                )
            except Exception as error_post_err:
                raise error_post_err


@router.post("/tick", status_code=202)
def process_digest(
    payload: DigestPayload,
    background_tasks: BackgroundTasks,
    token: str = Security(oauth2_scheme),
):
    background_tasks.add_task(generate_digest, payload, token)
    return JSONResponse(content={"status": "accepted"}, status_code=202)
