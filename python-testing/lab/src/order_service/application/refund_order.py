from uuid import UUID

from order_service.application.process_payment import OrderNotFound
from order_service.domain.order import InvalidOrderTransition, Order, OrderStatus
from order_service.ports.payment import PaymentDeclined, PaymentGateway
from order_service.ports.uow import UnitOfWorkFactory


class CapturedPaymentMissing(RuntimeError):
    pass


class RefundOrder:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        gateway: PaymentGateway,
    ) -> None:
        self._uow_factory = uow_factory
        self._gateway = gateway

    async def execute(self, order_id: UUID) -> Order:
        async with self._uow_factory() as uow:
            order = await uow.orders.get(order_id)
            if order is None:
                raise OrderNotFound(str(order_id))
            if order.status is OrderStatus.REFUNDED:
                return order
            if order.status not in {
                OrderStatus.PAID,
                OrderStatus.REFUND_IN_PROGRESS,
            }:
                raise InvalidOrderTransition(
                    f"cannot refund order from {order.status.name}"
                )
            if order.payment_reference is None:
                raise CapturedPaymentMissing("order has no captured payment")
            payment_reference = order.payment_reference
            if order.status is OrderStatus.PAID:
                order.start_refund()
                await uow.orders.save(order)
                await uow.commit()

        try:
            result = await self._gateway.refund(
                payment_reference=payment_reference,
                total=order.total,
                idempotency_key=f"refund:{order.id}",
            )
        except PaymentDeclined:
            async with self._uow_factory() as uow:
                declined = await uow.orders.get(order_id)
                if declined is None:
                    raise OrderNotFound(str(order_id))
                declined.mark_refund_declined()
                await uow.orders.save(declined)
                await uow.commit()
            raise

        async with self._uow_factory() as uow:
            refunded = await uow.orders.get(order_id)
            if refunded is None:
                raise OrderNotFound(str(order_id))
            if refunded.status is OrderStatus.REFUNDED:
                refunded.mark_refunded(result.reference)
                return refunded
            refunded.mark_refunded(result.reference)
            await uow.orders.save(refunded)
            await uow.commit()
            return refunded
