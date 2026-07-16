from order_service.application.create_order import CreateOrder
from order_service.application.refund_order import RefundOrder


def get_create_order() -> CreateOrder:
    raise RuntimeError("CreateOrder dependency is not configured")


def get_refund_order() -> RefundOrder:
    raise RuntimeError("RefundOrder dependency is not configured")
