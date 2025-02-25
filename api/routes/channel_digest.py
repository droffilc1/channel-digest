import os
import httpx
import logging
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Request,
    Security,
    Depends,
    HTTPException,
    Header,
)
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse
from collections import Counter
from typing import Optional

from api.db.schemas import DigestPayload


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

# Get the fallback token from environment variable
FALLBACK_TOKEN = os.environ.get("API_BEARER_TOKEN", "")


# Create a custom dependency function with enhanced logging
async def get_api_key(
    request: Request,
    api_key: Optional[str] = Security(api_key_header),
    authorization: Optional[str] = Header(None),
):
    # Log the request details for debugging
    logger.info(f"Request headers: {dict(request.headers)}")
    logger.info(f"API key from security: {api_key}")
    logger.info(f"Authorization header direct: {authorization}")

    # Try multiple sources for the token
    token = None

    # 1. Try from security dependency
    if api_key:
        token = (
            api_key.replace("Bearer ", "") if api_key.startswith("Bearer ") else api_key
        )
        logger.info(f"Using token from security dependency")

    # 2. Try from direct header
    elif authorization:
        token = (
            authorization.replace("Bearer ", "")
            if authorization.startswith("Bearer ")
            else authorization
        )
        logger.info(f"Using token from direct header")

    # 3. Try from environment variable
    elif FALLBACK_TOKEN:
        token = FALLBACK_TOKEN
        logger.info(f"Using fallback token from environment")

    # If still no token, try to get it from other common header variations
    if not token:
        headers = dict(request.headers)
        for key in headers:
            if key.lower() in [
                "auth",
                "authorization",
                "token",
                "api-key",
                "apikey",
                "x-api-key",
            ]:
                potential_token = headers[key]
                token = (
                    potential_token.replace("Bearer ", "")
                    if isinstance(potential_token, str)
                    and potential_token.startswith("Bearer ")
                    else potential_token
                )
                logger.info(f"Found token in alternate header: {key}")
                break

    # Check if we have a token
    if token:
        # Mask token in logs for security
        masked_token = token[:4] + "..." + token[-4:] if len(token) > 8 else "****"
        logger.info(f"Using token: {masked_token}")
        return token

    # If we reach here, no token was found
    logger.error("No API token found in any source")
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

    logger.info(f"Fetching users for org_id: {org_id}")

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
                logger.warning(f"Unexpected users API response: {data}")
                return 0
    except Exception as e:
        logger.error(f"Error fetching users: {str(e)}")
        raise e


async def fetch_messages(channel_id: str, token: str):
    url = f"https://api.telex.im/api/v1/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    params = {"limit": 50, "sort": "desc"}

    logger.info(f"Fetching messages for channel_id: {channel_id}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            # Check if "data" is None or not a dictionary
            if not isinstance(data.get("data"), dict):
                logger.warning("No valid data found in messages response")
                return []

            # Extract messages safely
            messages = data["data"].get("messages", [])
            if not isinstance(messages, list):
                logger.warning("Messages data not in expected list format")
                return []

            logger.info(f"Retrieved {len(messages)} messages")
            return messages

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        logger.error(f"Error fetching messages: {str(e)}")

    return []


async def generate_digest(payload: DigestPayload, token: str):
    logger.info(f"Generating digest for channel_id: {payload.channel_id}")
    try:
        user_count = await fetch_users(payload.organisation_id, token)
        messages = await fetch_messages(payload.channel_id, token)
        message_count = len(messages)

        logger.info(f"Found {user_count} users and {message_count} messages")

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

            logger.info(f"Trending keywords: {trending_keywords}")

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

        logger.info(f"Sending digest to: {payload.return_url}")

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
                logger.info("Digest sent successfully")
            except Exception as e:
                logger.error(f"Error sending digest: {str(e)}")
                raise
    except Exception as e:
        logger.error(f"Error generating digest: {str(e)}")


# Allow both POST and GET methods for more flexibility during testing
@router.post("/tick", status_code=202)
@router.get("/tick", status_code=202)
async def process_digest(
    request: Request,
    background_tasks: BackgroundTasks,
    payload: Optional[DigestPayload] = None,
    token: str = Depends(get_api_key),
):
    logger.info(f"Received request to /tick endpoint")

    # Try to get payload from request body if not provided
    if payload is None:
        try:
            body = await request.json()
            # Attempt to create a DigestPayload from the body
            # This depends on your DigestPayload schema
            # You may need to adjust this based on your actual schema
            payload = DigestPayload(**body)
            logger.info(f"Extracted payload from request body")
        except Exception as e:
            logger.error(f"Error parsing request body: {str(e)}")
            # For testing, you might want to use a default payload
            # Otherwise, return an error
            raise HTTPException(status_code=400, detail="Invalid payload format")

    logger.info(f"Processing digest with payload: {payload}")
    background_tasks.add_task(generate_digest, payload, token)
    return JSONResponse(content={"status": "accepted"}, status_code=202)
