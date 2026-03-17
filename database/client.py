"""
Supabase client — single shared instance used by the whole application.
"""

from __future__ import annotations

import logging

from supabase import create_client, Client

from config import SUPABASE

logger = logging.getLogger(__name__)

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        if not SUPABASE["url"] or not SUPABASE["key"]:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_KEY must be set in the environment."
            )
        _client = create_client(SUPABASE["url"], SUPABASE["key"])
        logger.info("Supabase client initialised (url=%s)", SUPABASE["url"])
    return _client
