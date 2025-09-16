import os
from typing import Optional

from supabase import create_client, Client

try:
    import httpx  # Optional, used for future custom client injection
except Exception:
    httpx = None  # type: ignore

_SUPABASE_SINGLETON: Optional[Client] = None


def get_supabase_client() -> Client:

    global _SUPABASE_SINGLETON
    if _SUPABASE_SINGLETON is not None:
        return _SUPABASE_SINGLETON

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")

    if not supabase_url:
        raise ValueError("SUPABASE_URL environment variable is required. Please check your .env file.")
    if not supabase_key:
        raise ValueError("SUPABASE_ANON_KEY environment variable is required. Please check your .env file.")

    # Future: if supabase-py exposes http client injection, configure keep-alive pool here.
    # For now, create default client (library reuses http connections internally where possible).
    _SUPABASE_SINGLETON = create_client(supabase_url, supabase_key)
    return _SUPABASE_SINGLETON


