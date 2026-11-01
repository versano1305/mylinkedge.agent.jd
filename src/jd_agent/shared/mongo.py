"""MongoDB helpers for LangGraph checkpoints only.

JD / application data lives in Postgres / Supabase; do not add Mongo document
loaders here.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv
from langgraph.checkpoint.mongodb import MongoDBSaver
from pymongo import MongoClient

DEFAULT_CHECKPOINT_COLLECTION = "checkpoints"
DEFAULT_CHECKPOINT_WRITES_COLLECTION = "checkpoint_writes"


def _get_env(name: str, *fallback_names: str) -> str | None:
    """Return the first non-empty environment variable among aliases."""
    for key in (name, *fallback_names):
        value = os.getenv(key)
        if value:
            return value
    return None


@lru_cache(maxsize=1)
def get_mongo_client() -> MongoClient[Any]:
    """Return a cached MongoDB client from environment variables."""
    load_dotenv()
    mongo_uri = _get_env("MONGODB_URI", "MONGO_URI")
    if not mongo_uri:
        raise ValueError("Missing MONGODB_URI/MONGO_URI environment variable.")
    return MongoClient(mongo_uri)


def _get_mongo_db_name() -> str:
    """Return the configured MongoDB database name."""
    load_dotenv()
    db_name = _get_env("MONGODB_DB", "MONGO_DB_NAME")
    if not db_name:
        raise ValueError("Missing MONGODB_DB/MONGO_DB_NAME environment variable.")
    return db_name


def get_mongo_checkpointer() -> MongoDBSaver:
    """Return a MongoDB checkpointer for multi-turn thread persistence.

    Uses ``MONGODB_URI`` / ``MONGODB_DB``. Optional overrides:
    ``MONGODB_CHECKPOINT_DB``, ``MONGODB_CHECKPOINT_COLLECTION``,
    ``MONGODB_CHECKPOINT_WRITES_COLLECTION``.
    """
    load_dotenv()
    db_name = _get_env("MONGODB_CHECKPOINT_DB") or _get_mongo_db_name()
    checkpoint_collection = (
        _get_env("MONGODB_CHECKPOINT_COLLECTION") or DEFAULT_CHECKPOINT_COLLECTION
    )
    writes_collection = (
        _get_env("MONGODB_CHECKPOINT_WRITES_COLLECTION")
        or DEFAULT_CHECKPOINT_WRITES_COLLECTION
    )
    return MongoDBSaver(
        get_mongo_client(),
        db_name=db_name,
        checkpoint_collection_name=checkpoint_collection,
        writes_collection_name=writes_collection,
    )
