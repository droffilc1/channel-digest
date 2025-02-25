import os
import httpx
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Request,
    Security,
    Depends,
    HTTPException,
)
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse
from collections import Counter

from api.db.schemas import DigestPayload


router = APIRouter()

api_key_header = APIKeyHeader(name="Authorization")

# Get the fallback token from environment variable
FALLBACK_TOKEN = os.environ.get("API_BEARER_TOKEN", "")


# Create a custom dependency function for token handling
def get_api_key(api_key: str = Security(api_key_header)):
    # Try to use the provided header first
    if api_key:
        return (
            api_key.replace("Bearer ", "") if api_key.startswith("Bearer ") else api_key
        )

    # If no API key in header or it's empty, use the fallback
    if FALLBACK_TOKEN:
        return FALLBACK_TOKEN

    # If no fallback either, raise an exception
    raise HTTPException(status_code=403, detail="API key required")


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


async def fetch_users(org_id: str, token: str):
    url = f"https://api.telex.im/api/v1/organisations/{org_id}/users"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()
            # Handle the nested data structure
            if (
                isinstance(data, dict)
                and "data" in data
                and isinstance(data["data"], list)
            ):
                return len(data["data"])  # Return count of users in data list
            elif (
                isinstance(data, dict)
                and "data" in data
                and isinstance(data["data"], dict)
            ):
                # Some APIs nest data even further
                users = data["data"].get("users", [])
                return len(users)
            else:
                print(f"Unexpected users API response: {data}")
                return 0
    except Exception as e:
        raise e


async def fetch_messages(channel_id: str, token: str):
    url = f"https://api.telex.im/api/v1/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    params = {"limit": 50, "sort": "desc"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            # Check if "data" is None or not a dictionary
            if not isinstance(data.get("data"), dict):
                return []

            # Extract messages safely
            messages = data["data"].get("messages", [])
            if not isinstance(messages, list):
                return []

            return messages

    except httpx.HTTPStatusError as e:
        print(f"HTTP error: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        print(f"Error fetching messages: {e}")

    return []


async def generate_digest(payload: DigestPayload, token: str):
    try:
        user_count = await fetch_users(payload.organisation_id, token)
        messages = await fetch_messages(payload.channel_id, token)
        message_count = len(messages)

        trending_keywords = []
        if messages:
            all_text = " ".join([msg.get("content", "") for msg in messages])
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
            word_counts = Counter(words)
            trending_keywords = [word for word, _ in word_counts.most_common(5)]

        message = (
            f"📊 Channel Digest Report\n\n"
            f"📨 Messages: {message_count}\n"
            f"👥 Active Users: {user_count}\n"
            f"🔍 Activity Status: {'Quiet - No messages yet' if message_count == 0 else 'Active'}"
        )
        if trending_keywords:
            message += f"\n🔥 Trending Keywords: {', '.join(trending_keywords)}"

        data = {
            "event_name": "Channel Digest Report",
            "message": message,
            "status": "success",
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
            except Exception as e:
                print(f"Error sending digest: {e}")
                raise
    except Exception as e:
        print(f"Error generating digest: {e}")


@router.post("/tick", status_code=202)
async def process_digest(
    payload: DigestPayload,
    background_tasks: BackgroundTasks,
    token: str = Depends(get_api_key),
):
    background_tasks.add_task(generate_digest, payload, token)
    return JSONResponse(content={"status": "accepted"}, status_code=202)
