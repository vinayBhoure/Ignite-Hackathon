"""Shared Neo4j driver, reused by api/, ui/ and core/ (CLAUDE.md: core/db/client.py is shared).

One driver per process; AuraDB Free can pause on inactivity, so callers should
expect occasional cold-start latency on the first query after idle time.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator

from neo4j import Driver, GraphDatabase, Session

_driver: Driver | None = None


class MissingNeo4jConfig(RuntimeError):
    pass


def get_driver() -> Driver:
    global _driver
    if _driver is None:
        uri = os.getenv("NEO4J_URI")
        user = os.getenv("NEO4J_USERNAME")
        password = os.getenv("NEO4J_PASSWORD")
        if not uri or not user or not password:
            raise MissingNeo4jConfig(
                "NEO4J_URI, NEO4J_USERNAME and NEO4J_PASSWORD must all be set (see .env.example)"
            )
        # Only surface real warnings: "unknown property" notices fire on every
        # poll until an optional property (e.g. Alert.simulated) first exists.
        _driver = GraphDatabase.driver(
            uri, auth=(user, password), notifications_disabled_classifications=["UNRECOGNIZED"]
        )
    return _driver


@contextmanager
def get_session() -> Iterator[Session]:
    with get_driver().session() as session:
        yield session


def close_driver() -> None:
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


# The ETL stored every ZoneReading.ts with a +05:30 offset. Neo4j compares
# zoned datetimes for *equality* including the offset (10:00+05:30 !=
# 04:30Z, though ordering works), so any value matched against ts or
# PASSES_THROUGH.bucket must be sent in this offset or it silently misses.
DATA_TZ = timezone(timedelta(hours=5, minutes=30))


def to_data_tz(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(DATA_TZ)


def to_utc(value) -> datetime:
    """neo4j.time.DateTime (or a plain datetime) -> tz-aware UTC datetime.

    Pydantic rejects neo4j's own temporal type, so every value read back from
    a ts-typed property must pass through this before going into a schema.
    """
    if hasattr(value, "to_native"):
        value = value.to_native()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
