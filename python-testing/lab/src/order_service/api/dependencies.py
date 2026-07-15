from order_service.application.create_order import CreateOrder


def get_create_order() -> CreateOrder:
    raise RuntimeError("CreateOrder dependency is not configured")
