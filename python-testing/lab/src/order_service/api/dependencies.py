from order_service.application.create_order import CreateOrder
from order_service.application.legacy_refund import LegacyRefund


def get_create_order() -> CreateOrder:
    raise RuntimeError("CreateOrder dependency is not configured")


def get_legacy_refund() -> LegacyRefund:
    raise RuntimeError("LegacyRefund dependency is not configured")
