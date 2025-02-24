import httpx
from fastapi import APIRouter, BackgroundTasks, Request, Security
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse

from api.db.schemas import DigestPayload

router = APIRouter()

api_key_header = APIKeyHeader(name="Authorization")


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
                "app_logo": "https://github.com/user-attachments/assets/f6907df9-dbaa-4c0b-9a51-3b1762ecd9ee",
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
    params = {"limit": 100}

    try:
        async with httpx.AsyncClient() as client:
            # First, get basic channel info
            channel = None

            # Try direct endpoint first
            direct_url = f"{api_url}/{channel_id}"
            try:
                response = await client.get(direct_url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    channel = data.get("data", {}).get("channel")
            except Exception:
                pass

            # If direct fetch fails, try paginated list
            if not channel:
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
                        (ch for ch in channels if ch.get("channels_id") == channel_id),
                        None,
                    )

                    if channel:
                        break

                    page += 1

            if not channel:
                return None

            # Now fetch trending keywords using messages API
            messages_url = f"{api_url}/{channel_id}/messages"
            try:
                msg_response = await client.get(
                    messages_url,
                    headers=headers,
                    params={"limit": 50, "sort": "desc"},
                    timeout=10,
                )

                if msg_response.status_code == 200:
                    msg_data = msg_response.json()
                    messages = msg_data.get("data", {}).get("messages", [])

                    # Extract text from messages
                    all_text = " ".join([msg.get("text", "") for msg in messages])

                    # Simple keyword extraction
                    if all_text:
                        # Remove common words
                        common_words = {
                            "the",
                            "a",
                            "an",
                            "and",
                            "or",
                            "but",
                            "in",
                            "on",
                            "at",
                            "to",
                            "for",
                            "is",
                            "are",
                            "was",
                            "were",
                        }
                        words = [
                            word.lower()
                            for word in all_text.split()
                            if len(word) > 3 and word.lower() not in common_words
                        ]

                        # Count word frequencies
                        from collections import Counter

                        word_counts = Counter(words)

                        # Get top 5 keywords
                        trending_keywords = [
                            word for word, _ in word_counts.most_common(5)
                        ]

                        # Add trending keywords to channel data
                        channel["trending_keywords"] = trending_keywords
                    else:
                        channel["trending_keywords"] = []
            except Exception:
                channel["trending_keywords"] = []

            return channel

    except Exception:
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
            trending_keywords = channel.get("trending_keywords", [])

            # Build the digest message
            message = (
                f"📊 Channel Digest Report for #{channel_name}\n\n"
                f"📨 Messages: {message_count}\n"
                f"👥 Active Users: {user_count}\n"
                f"🔍 Activity Status: {'Quiet - No messages yet' if message_count == 0 else 'Active'}"
            )

            # Add trending keywords if available
            if trending_keywords:
                message += f"\n🔥 Trending Keywords: {', '.join(trending_keywords)}"

            status = "success"

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
            except Exception:
                raise

    except Exception as e:
        error_data = {
            "event_name": "Channel Digest Report",
            "message": f"Error generating digest: {str(e)}",
            "status": "error",
            "username": "Channel Digest",
        }
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
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
async def process_digest(
    payload: DigestPayload,
    background_tasks: BackgroundTasks,
    api_key: str = Security(api_key_header),
):
    # Extract token (remove 'Bearer ' prefix if present)
    token = api_key
    if api_key.startswith("Bearer "):
        token = api_key.replace("Bearer ", "")

    background_tasks.add_task(generate_digest, payload, token)
    return JSONResponse(content={"status": "accepted"}, status_code=202)
