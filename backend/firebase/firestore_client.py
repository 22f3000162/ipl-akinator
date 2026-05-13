"""
firebase/firestore_client.py

Singleton Firestore client.
Uses GOOGLE_APPLICATION_CREDENTIALS env var for service account auth.
Falls back to a local JSON file mode when running without Firebase
(useful for local dev before service account is set up).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

_db = None
_using_mock = False


def get_db():
    """
    Return a Firestore client (singleton).
    If Firebase credentials are not configured, returns a MockDB
    that stores data in memory (for local dev / Phase 1 testing).
    """
    global _db, _using_mock

    if _db is not None:
        return _db

    # 1. Try JSON string from env (Production/Vercel)
    json_creds = os.getenv("FIREBASE_CREDENTIALS_JSON", "")
    if json_creds:
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore
            if not firebase_admin._apps:
                info = json.loads(json_creds)
                cred = credentials.Certificate(info)
                firebase_admin.initialize_app(cred)
            _db = firestore.client()
            logger.info("Firestore connected via FIREBASE_CREDENTIALS_JSON")
            return _db
        except Exception as exc:
            logger.warning("Firestore init via JSON string failed: %s", exc)

    # 2. Try file path (Local dev)
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    if creds_path and Path(creds_path).exists():
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore

            if not firebase_admin._apps:
                cred = credentials.Certificate(creds_path)
                firebase_admin.initialize_app(cred)

            _db = firestore.client()
            logger.info("Firestore connected via service account: %s", creds_path)
            return _db

        except Exception as exc:
            logger.warning("Firestore init via file failed (%s)", exc)

    # Fallback: in-memory mock for local dev
    logger.warning(
        "No Firebase credentials found. Using in-memory MockDB. "
        "Set GOOGLE_APPLICATION_CREDENTIALS in .env to use real Firestore."
    )
    _using_mock = True
    _db = MockDB()
    return _db


def is_using_mock() -> bool:
    return _using_mock


# ─────────────────────────────────────────────────────────────────────────────
# In-memory MockDB — mirrors Firestore's collection/document API
# Enables full local dev without Firebase credentials
# ─────────────────────────────────────────────────────────────────────────────

class MockDocRef:
    def __init__(self, store: dict, path: str):
        self._store = store
        self._path = path

    def set(self, data: dict, merge: bool = False) -> None:
        if merge and self._path in self._store:
            self._store[self._path].update(data)
        else:
            self._store[self._path] = dict(data)

    def get(self) -> "MockDocSnapshot":
        data = self._store.get(self._path)
        return MockDocSnapshot(exists=data is not None, data=data or {})

    def update(self, data: dict) -> None:
        if self._path in self._store:
            self._store[self._path].update(data)
        else:
            self._store[self._path] = dict(data)

    def collection(self, name: str) -> "MockCollectionRef":
        return MockCollectionRef(self._store, f"{self._path}/{name}")


class MockDocSnapshot:
    def __init__(self, exists: bool, data: dict):
        self.exists = exists
        self._data = data

    def to_dict(self) -> dict:
        return self._data


class MockCollectionRef:
    def __init__(self, store: dict, prefix: str):
        self._store = store
        self._prefix = prefix

    def document(self, doc_id: str) -> MockDocRef:
        return MockDocRef(self._store, f"{self._prefix}/{doc_id}")

    def add(self, data: dict) -> tuple[Any, MockDocRef]:
        import uuid
        doc_id = str(uuid.uuid4())[:8]
        ref = self.document(doc_id)
        ref.set(data)
        return (None, ref)


class MockDB:
    def __init__(self):
        self._store: dict[str, dict] = {}

    def collection(self, name: str) -> MockCollectionRef:
        return MockCollectionRef(self._store, name)
