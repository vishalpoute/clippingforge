"""Tests for ClipForge AI database layer."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db


def test_engine_creates_with_sqlite() -> None:
    """An in-memory SQLite engine should be constructible."""
    eng = create_engine("sqlite:///:memory:", echo=False)
    assert eng is not None
    with eng.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1


def test_tables_created() -> None:
    """All models registered on Base should produce tables."""
    import app.models  # noqa: F401  — ensure models are imported

    eng = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=eng)

    with eng.connect() as conn:
        # SQLite-specific: query the master table list
        rows = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        table_names = {r[0] for r in rows}
        assert "users" in table_names
        assert "projects" in table_names


def test_get_db_yields_session() -> None:
    """get_db should yield a usable session and close it."""
    gen = get_db()
    session = next(gen)
    assert session is not None
    # Execute a simple query to prove the session works
    result = session.execute(text("SELECT 1"))
    assert result.scalar() == 1
    # Finish the generator (triggers close)
    try:
        next(gen)
    except StopIteration:
        pass
