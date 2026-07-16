import pytest
from alembic import command
from sqlalchemy import Boolean, CHAR, DateTime, Integer, Numeric, Text, inspect
from sqlalchemy.dialects.postgresql import JSONB, UUID

pytestmark = [pytest.mark.integration, pytest.mark.docker]


@pytest.mark.asyncio(loop_scope="session")
async def test_upgrade_creates_exact_orders_and_outbox_schema(
    alembic_config, async_engine
) -> None:
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    async with async_engine.connect() as connection:
        metadata = await connection.run_sync(_inspect_schema)

    assert metadata["tables"] == {"alembic_version", "orders", "outbox_messages"}
    assert metadata["orders"] == {
        "id", "idempotency_key", "amount", "currency", "status", "created_at",
        "payment_reference", "refund_reference", "version",
    }
    assert metadata["outbox_messages"] == {
        "id", "topic", "aggregate_id", "payload", "occurred_at", "attempts",
        "available_at", "claimed_at", "done",
    }
    assert metadata["primary_keys"] == {
        "orders": {"name": "orders_pkey", "columns": ("id",)},
        "outbox_messages": {
            "name": "outbox_messages_pkey",
            "columns": ("id",),
        },
    }
    assert metadata["unique_constraints"] == {
        "orders": {("uq_orders_idempotency_key", ("idempotency_key",))},
        "outbox_messages": set(),
    }
    assert metadata["indexes"] == {
        "orders": set(),
        "outbox_messages": {
            (
                "ix_outbox_messages_dispatch",
                ("done", "available_at", "claimed_at"),
                False,
            )
        },
    }
    assert metadata["check_constraints"] == {"orders": set(), "outbox_messages": set()}
    assert metadata["foreign_keys"] == {"orders": [], "outbox_messages": []}
    assert metadata["column_contracts"] == {
        "orders": {
            "id": (("UUID",), False, None),
            "idempotency_key": (("TEXT",), False, None),
            "amount": (("NUMERIC", 18, 2), False, None),
            "currency": (("CHAR", 3), False, None),
            "status": (("TEXT",), False, None),
            "created_at": (("TIMESTAMP", True), False, None),
            "payment_reference": (("TEXT",), True, None),
            "refund_reference": (("TEXT",), True, None),
            "version": (("INTEGER",), False, None),
        },
        "outbox_messages": {
            "id": (("UUID",), False, None),
            "topic": (("TEXT",), False, None),
            "aggregate_id": (("UUID",), False, None),
            "payload": (("JSONB",), False, None),
            "occurred_at": (("TIMESTAMP", True), False, None),
            "attempts": (("INTEGER",), False, "0"),
            "available_at": (("TIMESTAMP", True), True, None),
            "claimed_at": (("TIMESTAMP", True), True, None),
            "done": (("BOOLEAN",), False, "false"),
        },
    }


def _inspect_schema(connection):
    inspector = inspect(connection)
    order_columns = {column["name"]: column for column in inspector.get_columns("orders")}
    outbox_columns = {
        column["name"]: column for column in inspector.get_columns("outbox_messages")
    }
    return {
        "tables": set(inspector.get_table_names()),
        "orders": {column["name"] for column in inspector.get_columns("orders")},
        "outbox_messages": {
            column["name"] for column in inspector.get_columns("outbox_messages")
        },
        "primary_keys": {
            table: {
                "name": inspector.get_pk_constraint(table)["name"],
                "columns": tuple(inspector.get_pk_constraint(table)["constrained_columns"]),
            }
            for table in ("orders", "outbox_messages")
        },
        "unique_constraints": {
            table: {
                (constraint["name"], tuple(constraint["column_names"]))
                for constraint in inspector.get_unique_constraints(table)
            }
            for table in ("orders", "outbox_messages")
        },
        "indexes": {
            table: {
                (index["name"], tuple(index["column_names"]), index["unique"])
                for index in inspector.get_indexes(table)
                if "duplicates_constraint" not in index
            }
            for table in ("orders", "outbox_messages")
        },
        "check_constraints": {
            table: {
                (constraint["name"], constraint["sqltext"])
                for constraint in inspector.get_check_constraints(table)
            }
            for table in ("orders", "outbox_messages")
        },
        "foreign_keys": {
            table: inspector.get_foreign_keys(table)
            for table in ("orders", "outbox_messages")
        },
        "column_contracts": {
            "orders": {
                name: (_type_contract(column["type"]), column["nullable"], column["default"])
                for name, column in order_columns.items()
            },
            "outbox_messages": {
                name: (_type_contract(column["type"]), column["nullable"], column["default"])
                for name, column in outbox_columns.items()
            },
        },
    }


def _type_contract(column_type):
    if isinstance(column_type, UUID):
        return ("UUID",)
    if isinstance(column_type, JSONB):
        return ("JSONB",)
    if isinstance(column_type, Numeric):
        return ("NUMERIC", column_type.precision, column_type.scale)
    if isinstance(column_type, CHAR):
        return ("CHAR", column_type.length)
    if isinstance(column_type, DateTime):
        return ("TIMESTAMP", column_type.timezone)
    if isinstance(column_type, Boolean):
        return ("BOOLEAN",)
    if isinstance(column_type, Integer):
        return ("INTEGER",)
    if isinstance(column_type, Text):
        return ("TEXT",)
    raise AssertionError(f"unexpected reflected type: {column_type!r}")


@pytest.mark.asyncio(loop_scope="session")
async def test_downgrade_then_upgrade_is_reversible(alembic_config, async_engine) -> None:
    try:
        command.downgrade(alembic_config, "base")
        async with async_engine.connect() as connection:
            tables = await connection.run_sync(
                lambda sync_connection: set(inspect(sync_connection).get_table_names())
            )
        assert tables == {"alembic_version"}
    finally:
        command.upgrade(alembic_config, "head")


@pytest.mark.asyncio(loop_scope="session")
async def test_refund_migration_preserves_exact_0001_schema_on_downgrade(
    alembic_config, async_engine
) -> None:
    try:
        command.downgrade(alembic_config, "0001")
        async with async_engine.connect() as connection:
            before_refund = await connection.run_sync(_inspect_schema)
        assert before_refund["orders"] == {
            "id",
            "idempotency_key",
            "amount",
            "currency",
            "status",
            "created_at",
            "payment_reference",
            "version",
        }
        assert "refund_reference" not in before_refund["column_contracts"]["orders"]
        assert before_refund["tables"] == {
            "alembic_version",
            "orders",
            "outbox_messages",
        }
        assert before_refund["outbox_messages"] == {
            "id",
            "topic",
            "aggregate_id",
            "payload",
            "occurred_at",
            "attempts",
            "available_at",
            "claimed_at",
            "done",
        }
        assert before_refund["primary_keys"] == {
            "orders": {"name": "orders_pkey", "columns": ("id",)},
            "outbox_messages": {
                "name": "outbox_messages_pkey",
                "columns": ("id",),
            },
        }
        assert before_refund["unique_constraints"] == {
            "orders": {("uq_orders_idempotency_key", ("idempotency_key",))},
            "outbox_messages": set(),
        }
        assert before_refund["indexes"] == {
            "orders": set(),
            "outbox_messages": {
                (
                    "ix_outbox_messages_dispatch",
                    ("done", "available_at", "claimed_at"),
                    False,
                )
            },
        }
        assert before_refund["check_constraints"] == {
            "orders": set(),
            "outbox_messages": set(),
        }
        assert before_refund["foreign_keys"] == {
            "orders": [],
            "outbox_messages": [],
        }
        assert before_refund["column_contracts"] == {
            "orders": {
                "id": (("UUID",), False, None),
                "idempotency_key": (("TEXT",), False, None),
                "amount": (("NUMERIC", 18, 2), False, None),
                "currency": (("CHAR", 3), False, None),
                "status": (("TEXT",), False, None),
                "created_at": (("TIMESTAMP", True), False, None),
                "payment_reference": (("TEXT",), True, None),
                "version": (("INTEGER",), False, None),
            },
            "outbox_messages": {
                "id": (("UUID",), False, None),
                "topic": (("TEXT",), False, None),
                "aggregate_id": (("UUID",), False, None),
                "payload": (("JSONB",), False, None),
                "occurred_at": (("TIMESTAMP", True), False, None),
                "attempts": (("INTEGER",), False, "0"),
                "available_at": (("TIMESTAMP", True), True, None),
                "claimed_at": (("TIMESTAMP", True), True, None),
                "done": (("BOOLEAN",), False, "false"),
            },
        }

        command.upgrade(alembic_config, "head")
        async with async_engine.connect() as connection:
            after_refund = await connection.run_sync(_inspect_schema)
        assert after_refund["orders"] == before_refund["orders"] | {
            "refund_reference"
        }
        assert after_refund["column_contracts"]["orders"]["refund_reference"] == (
            ("TEXT",),
            True,
            None,
        )
    finally:
        command.upgrade(alembic_config, "head")
