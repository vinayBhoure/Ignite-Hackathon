"""Shared Neo4j driver, reused by api/, ui/ and core/ (CLAUDE.md: core/db/client.py is shared).

One driver per process; AuraDB Free can pause on inactivity, so callers should
expect occasional cold-start latency on the first query after idle time.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
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
        _driver = GraphDatabase.driver(uri, auth=(user, password))
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
