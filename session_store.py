"""
In-memory session store for OAuth credentials.

NOTE: This is intentionally simple for a take-home demo.
In production, replace this with Redis or a database-backed store
with TTL support and encrypted token storage.
"""

import secrets
from typing import Optional

from google.oauth2.credentials import Credentials

# session_id → Google OAuth credentials
# Scoped to process lifetime — restarts clear all sessions.
_store: dict[str, Credentials] = {}


def create_session(credentials: Credentials) -> str:
    """Store credentials and return a new session ID."""
    session_id = secrets.token_urlsafe(16)
    _store[session_id] = credentials
    return session_id


def get_credentials(session_id: str) -> Optional[Credentials]:
    """Return credentials for session_id, or None if not found."""
    return _store.get(session_id)


def delete_session(session_id: str) -> None:
    """Remove a session."""
    _store.pop(session_id, None)
