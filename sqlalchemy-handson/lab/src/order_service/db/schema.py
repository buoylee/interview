from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)
CENT = Decimal("0.01")


class Money(TypeDecorator[Decimal]):
    impl = Numeric(12, 2)
    cache_ok = True

    def process_bind_param(self, value: Decimal | None, dialect: Dialect) -> Decimal | None:
        del dialect
        if value is None:
            return None
        if not isinstance(value, Decimal):
            raise TypeError("Money values must be Decimal")
        return value.quantize(CENT, rounding=ROUND_HALF_EVEN)


tenants = Table(
    "tenants",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("name", String(120), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

products = Table(
    "products",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False),
    Column("sku", String(64), nullable=False),
    Column("name", String(200), nullable=False),
    Column("unit_price", Money(), nullable=False),
    Column("attributes", JSONB, nullable=False, server_default="{}"),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("tenant_id", "id"),
    UniqueConstraint("tenant_id", "sku"),
    CheckConstraint("unit_price >= 0", name="unit_price_nonnegative"),
)

inventories = Table(
    "inventories",
    metadata,
    Column("tenant_id", Uuid(as_uuid=True), primary_key=True),
    Column("product_id", Uuid(as_uuid=True), primary_key=True),
    Column("available", Integer, nullable=False, server_default="0"),
    Column("reserved", Integer, nullable=False, server_default="0"),
    Column("version", Integer, nullable=False, server_default="1"),
    ForeignKeyConstraint(
        ["tenant_id", "product_id"],
        ["products.tenant_id", "products.id"],
    ),
    CheckConstraint("available >= 0", name="available_nonnegative"),
    CheckConstraint("reserved >= 0", name="reserved_nonnegative"),
    CheckConstraint("reserved <= available", name="reserved_not_above_available"),
    CheckConstraint("version > 0", name="version_positive"),
)

orders = Table(
    "orders",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False),
    Column("status", String(24), nullable=False),
    Column("total", Money(), nullable=False),
    Column("idempotency_key", String(120), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("tenant_id", "id"),
    UniqueConstraint("tenant_id", "idempotency_key"),
    CheckConstraint(
        "status IN ('pending', 'confirmed', 'cancelled')",
        name="known_status",
    ),
    CheckConstraint("total >= 0", name="total_nonnegative"),
)

order_lines = Table(
    "order_lines",
    metadata,
    Column("tenant_id", Uuid(as_uuid=True), primary_key=True),
    Column("order_id", Uuid(as_uuid=True), primary_key=True),
    Column("line_number", Integer, primary_key=True),
    Column("product_id", Uuid(as_uuid=True), nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("unit_price", Money(), nullable=False),
    ForeignKeyConstraint(["tenant_id", "order_id"], ["orders.tenant_id", "orders.id"]),
    ForeignKeyConstraint(
        ["tenant_id", "product_id"],
        ["products.tenant_id", "products.id"],
    ),
    CheckConstraint("line_number > 0", name="line_number_positive"),
    CheckConstraint("quantity > 0", name="quantity_positive"),
    CheckConstraint("unit_price >= 0", name="unit_price_nonnegative"),
)

inventory_reservations = Table(
    "inventory_reservations",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), nullable=False),
    Column("order_id", Uuid(as_uuid=True), nullable=False),
    Column("product_id", Uuid(as_uuid=True), nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("status", String(24), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    ForeignKeyConstraint(["tenant_id", "order_id"], ["orders.tenant_id", "orders.id"]),
    ForeignKeyConstraint(
        ["tenant_id", "product_id"],
        ["products.tenant_id", "products.id"],
    ),
    UniqueConstraint("tenant_id", "order_id", "product_id"),
    CheckConstraint("quantity > 0", name="quantity_positive"),
    CheckConstraint("status IN ('held', 'released', 'consumed')", name="known_status"),
)

idempotency_records = Table(
    "idempotency_records",
    metadata,
    Column("tenant_id", Uuid(as_uuid=True), primary_key=True),
    Column("key", String(120), primary_key=True),
    Column("request_hash", String(64), nullable=False),
    Column("resource_type", String(64), nullable=False),
    Column("resource_id", Uuid(as_uuid=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
)

outbox_events = Table(
    "outbox_events",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False),
    Column("aggregate_type", String(64), nullable=False),
    Column("aggregate_id", Uuid(as_uuid=True), nullable=False),
    Column("event_type", String(120), nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("status", String(24), nullable=False, server_default="pending"),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("available_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("locked_by", String(120)),
    Column("locked_at", DateTime(timezone=True)),
    Column("published_at", DateTime(timezone=True)),
    Column("last_error", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("status IN ('pending', 'publishing', 'published')", name="known_status"),
    CheckConstraint("attempts >= 0", name="attempts_nonnegative"),
)

Index(
    "ix_outbox_events_claimable",
    outbox_events.c.available_at,
    postgresql_where=outbox_events.c.status == "pending",
)
