from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from langgraph.checkpoint.postgres import PostgresSaver


def postgres_conninfo(database_url: str) -> str:
    if database_url.startswith("postgresql+psycopg://"):
        return database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    if database_url.startswith("postgresql://"):
        return database_url
    raise ValueError("database_url must use a PostgreSQL scheme")


@contextmanager
def open_postgres_checkpointer(database_url: str) -> Iterator[PostgresSaver]:
    with PostgresSaver.from_conn_string(postgres_conninfo(database_url)) as saver:
        yield saver
