"""Synchronous SQL ports and adapters used by room persistence."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any, Protocol, TypeVar, cast

from .errors import CorruptRoomStateError


_T = TypeVar("_T")


class SynchronousSqlExecutor(Protocol):
    """The complete SQL surface used by the room repository.

    ``exec`` intentionally mirrors Cloudflare's ``ctx.storage.sql.exec``
    binding convention. ``transaction`` must invoke the callback before it
    returns and roll back all writes if the callback raises.
    """

    def exec(self, statement: str, *bindings: Any) -> Any:
        """Execute one SQL statement and return a cursor-like value."""

    def transaction(self, callback: Callable[[], _T]) -> _T:
        """Run ``callback`` in one synchronous transaction."""


class CloudflareSqlExecutor:
    """Adapter for a SQLite-backed Durable Object's synchronous storage API."""

    def __init__(self, storage: Any) -> None:
        sql = getattr(storage, "sql", None)
        if sql is None or not callable(getattr(sql, "exec", None)):
            raise TypeError("Durable Object storage must expose storage.sql.exec")

        transaction_sync = getattr(storage, "transactionSync", None)
        if transaction_sync is None:
            transaction_sync = getattr(storage, "transaction_sync", None)
        if not callable(transaction_sync):
            raise TypeError(
                "Durable Object storage must expose synchronous transactionSync"
            )

        self._sql = sql
        self._transaction_sync = transaction_sync

    def exec(self, statement: str, *bindings: Any) -> Any:
        return self._sql.exec(statement, *bindings)

    def transaction(self, callback: Callable[[], _T]) -> _T:
        return cast(_T, self._transaction_sync(callback))


class _SQLiteCursorResult:
    """Small cursor facade matching the Cloudflare methods the repository uses."""

    def __init__(self, cursor: Any) -> None:
        description = cursor.description
        if description is None:
            self._rows: list[dict[str, Any]] = []
        else:
            names = [column[0] for column in description]
            self._rows = [
                dict(zip(names, row, strict=True)) for row in cursor.fetchall()
            ]
        self.rowsWritten = max(int(cursor.rowcount), 0)

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self._rows)

    def toArray(self) -> list[dict[str, Any]]:  # noqa: N802 - Cloudflare API spelling
        return list(self._rows)

    def one(self) -> dict[str, Any]:
        if len(self._rows) != 1:
            raise RuntimeError(f"expected exactly one SQL row, got {len(self._rows)}")
        return self._rows[0]


class SQLiteSqlExecutor:
    """Adapter for a CPython ``sqlite3.Connection``.

    The connection is switched to explicit autocommit mode so every repository
    transaction has an unambiguous BEGIN/COMMIT boundary. No import of
    ``sqlite3`` is needed at runtime; the supplied connection is intentionally
    duck typed.
    """

    def __init__(self, connection: Any) -> None:
        if not callable(getattr(connection, "execute", None)):
            raise TypeError("SQLite executor requires a DB-API connection")
        if bool(getattr(connection, "in_transaction", False)):
            raise ValueError("SQLite connection must not have an open transaction")
        try:
            connection.isolation_level = None
        except (AttributeError, TypeError) as exc:
            raise TypeError(
                "SQLite connection must support explicit transactions"
            ) from exc
        self._connection = connection

    def exec(self, statement: str, *bindings: Any) -> _SQLiteCursorResult:
        cursor = self._connection.execute(statement, tuple(bindings))
        return _SQLiteCursorResult(cursor)

    def transaction(self, callback: Callable[[], _T]) -> _T:
        if bool(getattr(self._connection, "in_transaction", False)):
            raise RuntimeError("nested repository transactions are not supported")

        self._connection.execute("BEGIN IMMEDIATE")
        try:
            result = callback()
        except BaseException:
            self._connection.rollback()
            raise
        else:
            self._connection.commit()
            return result


# A spelling-compatible alias for callers that prefer ``Sqlite``.
SqliteSqlExecutor = SQLiteSqlExecutor


def rows(cursor: Any) -> list[Any]:
    to_array = getattr(cursor, "toArray", None)
    if callable(to_array):
        return list(to_array())
    to_array = getattr(cursor, "to_array", None)
    if callable(to_array):
        return list(to_array())
    fetchall = getattr(cursor, "fetchall", None)
    if callable(fetchall):
        return list(fetchall())
    if isinstance(cursor, Iterable):
        return list(cursor)
    raise TypeError("SQL cursor does not expose a synchronous row iterator")


def one(cursor: Any) -> Any:
    exactly_one = getattr(cursor, "one", None)
    if callable(exactly_one):
        return exactly_one()
    values = rows(cursor)
    if len(values) != 1:
        raise CorruptRoomStateError(f"expected one SQL row, found {len(values)}")
    return values[0]


def row_value(row: Any, name: str) -> Any:
    if isinstance(row, Mapping):
        return row[name]
    try:
        return row[name]
    except (KeyError, TypeError, IndexError):
        try:
            return getattr(row, name)
        except AttributeError as exc:
            raise CorruptRoomStateError(f"SQL row is missing column {name!r}") from exc


def rows_written(cursor: Any) -> int | None:
    value = getattr(cursor, "rowsWritten", None)
    if value is None:
        value = getattr(cursor, "rows_written", None)
    if callable(value):
        value = value()
    return None if value is None else int(value)


__all__ = [
    "CloudflareSqlExecutor",
    "SQLiteSqlExecutor",
    "SqliteSqlExecutor",
    "SynchronousSqlExecutor",
]
