"""
Shared FastAPI dependencies.
Injected via Depends() into route handlers.
"""

import os

from fastapi import Header, HTTPException

API_KEY = os.getenv("API_KEY", "dev-api-key-change-in-production")


async def verify_api_key(x_api_key: str = Header(..., description="API key for authentication")) -> str:
    """
    Simple API key authentication.
    In production, swap this for JWT bearer token validation or OAuth2.
    """
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key
