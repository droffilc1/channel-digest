from fastapi import APIRouter

from api.routes import channel_digest

api_router = APIRouter()
api_router.include_router(channel_digest.router, prefix="", tags=["tick"])
