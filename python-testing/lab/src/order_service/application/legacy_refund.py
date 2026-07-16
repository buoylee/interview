from uuid import UUID

from order_service.application.process_payment import OrderNotFound
from order_service.domain.order import OrderStatus
from order_service.ports.payment import PaymentGateway
from order_service.ports.uow import UnitOfWorkFactory


class CapturedPaymentMissing(RuntimeError):
    pass


class LegacyRefund:
    def __init__(self, uow_factory: UnitOfWorkFactory, gateway: PaymentGateway) -> None:
        self._uow_factory = uow_factory
        self._gateway = gateway

    async def execute(self, order_id: UUID, request_id: str) -> None:
        async with self._uow_factory() as uow:
            order = await uow.orders.get(order_id)
            if order is None:
                raise OrderNotFound(str(order_id))
        if (
            order.status is not OrderStatus.PAID
            or order.payment_reference is None
        ):
            raise CapturedPaymentMissing("order has no captured payment")
        await self._gateway.refund(
            payment_reference=order.payment_reference,
            total=order.total,
            idempotency_key=request_id,
        )
