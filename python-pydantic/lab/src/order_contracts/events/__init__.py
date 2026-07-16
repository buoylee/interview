"""Versioned event contracts and parsing adapters."""

from order_contracts.events.envelope import OrderCreatedMessage, parse_order_created

__all__ = ["OrderCreatedMessage", "parse_order_created"]
