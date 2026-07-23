import os
import unittest
from datetime import UTC, datetime, timedelta, timezone

os.environ.setdefault("XIANYU_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("XIANYU_REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ.setdefault("XIANYU_JWT_SECRET", "test-secret-with-sufficient-length")

from sqlalchemy import Column, DateTime, Integer, MetaData, Table, create_engine, select
from sqlalchemy.dialects.mysql import dialect as mysql_dialect

from apps.api.xianyu_admin_api import orm  # noqa: F401
from apps.api.xianyu_admin_api.database import (
    Base,
    UTCDateTime,
    _set_mysql_session_timezone,
)
from apps.api.xianyu_admin_api.schemas import UserPayload


class _RecordingCursor:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.closed = False

    def execute(self, statement: str) -> None:
        self.statements.append(statement)

    def close(self) -> None:
        self.closed = True


class _RecordingConnection:
    def __init__(self) -> None:
        self.recording_cursor = _RecordingCursor()

    def cursor(self) -> _RecordingCursor:
        return self.recording_cursor


class TimezoneContractTests(unittest.TestCase):
    def test_every_orm_datetime_column_uses_utc_type(self) -> None:
        datetime_columns = [
            column
            for table in Base.metadata.tables.values()
            for column in table.columns
            if isinstance(column.type, UTCDateTime)
        ]

        self.assertGreater(len(datetime_columns), 100)
        self.assertFalse(
            [
                column
                for table in Base.metadata.tables.values()
                for column in table.columns
                if isinstance(column.type, DateTime)
            ]
        )

    def test_database_round_trip_restores_utc_awareness(self) -> None:
        metadata = MetaData()
        probe = Table(
            "timezone_probe",
            metadata,
            Column("probe_id", Integer, primary_key=True),
            Column("occurred_at", UTCDateTime(), nullable=False),
        )
        engine = create_engine("sqlite://")
        metadata.create_all(engine)
        beijing = timezone(timedelta(hours=8))

        try:
            with engine.begin() as connection:
                connection.execute(
                    probe.insert(),
                    [
                        {
                            "probe_id": 1,
                            "occurred_at": datetime(2026, 7, 16, 18, 0, tzinfo=beijing),
                        },
                        {
                            "probe_id": 2,
                            "occurred_at": datetime(2026, 7, 16, 10, 0),
                        },
                    ],
                )
            with engine.connect() as connection:
                values = connection.scalars(
                    select(probe.c.occurred_at).order_by(probe.c.probe_id)
                ).all()
        finally:
            engine.dispose()

        expected = datetime(2026, 7, 16, 10, 0, tzinfo=UTC)
        self.assertEqual(values, [expected, expected])
        self.assertTrue(all(value.tzinfo is UTC for value in values))

    def test_mysql_millisecond_datetime_uses_fractional_precision(self) -> None:
        resolved = UTCDateTime(precision=3).load_dialect_impl(mysql_dialect())

        self.assertEqual(resolved.fsp, 3)

    def test_sqlite_round_trip_preserves_milliseconds(self) -> None:
        metadata = MetaData()
        probe = Table(
            "millisecond_probe",
            metadata,
            Column("probe_id", Integer, primary_key=True),
            Column("occurred_at", UTCDateTime(precision=3), nullable=False),
        )
        engine = create_engine("sqlite://")
        expected = datetime(2026, 7, 17, 10, 0, 0, 123000, tzinfo=UTC)
        metadata.create_all(engine)

        try:
            with engine.begin() as connection:
                connection.execute(
                    probe.insert(), {"probe_id": 1, "occurred_at": expected}
                )
            with engine.connect() as connection:
                actual = connection.scalar(select(probe.c.occurred_at))
        finally:
            engine.dispose()

        self.assertEqual(actual, expected)

    def test_api_models_emit_explicit_utc_datetimes(self) -> None:
        beijing = timezone(timedelta(hours=8))
        payload = UserPayload(
            user_id="user-1",
            username="operator",
            created_at=datetime(2026, 7, 16, 10, 0),
            updated_at=datetime(2026, 7, 16, 18, 0, tzinfo=beijing),
        )

        self.assertEqual(
            payload.created_at,
            datetime(2026, 7, 16, 10, 0, tzinfo=UTC),
        )
        self.assertEqual(payload.updated_at, payload.created_at)
        serialized = payload.model_dump(mode="json")
        self.assertEqual(serialized["created_at"], "2026-07-16T10:00:00Z")
        self.assertEqual(serialized["updated_at"], "2026-07-16T10:00:00Z")

    def test_mysql_connections_are_pinned_to_utc(self) -> None:
        connection = _RecordingConnection()

        _set_mysql_session_timezone(connection, None)

        self.assertEqual(
            connection.recording_cursor.statements,
            ["SET SESSION time_zone = '+00:00'"],
        )
        self.assertTrue(connection.recording_cursor.closed)


if __name__ == "__main__":
    unittest.main()
