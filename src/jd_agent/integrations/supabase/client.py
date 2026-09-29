"""Supabase client factory for the JD agent (secret key, bypasses RLS)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from supabase import Client, create_client


@dataclass(frozen=True)
class SupabaseSettings:
    """Env-backed Supabase project settings (server-only secret key)."""

    url: str
    secret_key: str

    @classmethod
    def from_env(cls) -> SupabaseSettings:
        url = os.getenv("SUPABASE_URL", "").strip()
        secret_key = os.getenv("SUPABASE_SECRET_KEY", "").strip()
        missing = [
            name
            for name, value in (
                ("SUPABASE_URL", url),
                ("SUPABASE_SECRET_KEY", secret_key),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"Missing {', '.join(missing)}")
        return cls(url=url, secret_key=secret_key)


def create_supabase_client(
    *,
    settings: SupabaseSettings | None = None,
) -> Client:
    """Create a Supabase client with the project secret key.

    Secret keys map to the ``service_role`` Postgres role and bypass RLS.
    Use only in server-side agent runtimes; never ship this key to clients.
    See https://supabase.com/docs/guides/getting-started/api-keys#secret-keys-and-elevated-access
    """
    cfg = settings or SupabaseSettings.from_env()
    return create_client(cfg.url, cfg.secret_key)


def client_from_env() -> Client:
    """Build a secret-key client from ``SUPABASE_*`` environment variables."""
    return create_supabase_client()
