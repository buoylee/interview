from uuid import UUID

from order_service.domain.order import InvalidOrderTransition, Order, OrderStatus
from order_service.ports.payment import PaymentDeclined, PaymentGateway, PaymentUncertain
from order_service.ports.uow import UnitOfWorkFactory


class OrderNotFound(LookupError):
    pass


class ProcessPayment:
    def __init__(self, uow_factory: UnitOfWorkFactory, gateway: PaymentGateway) -> None:
        self._uow_factory = uow_factory
        self._gateway = gateway

    async def execute(self, order_id: UUID) -> Order:
        async with self._uow_factory() as uow:
            order = await uow.orders.get(order_id)
            if order is None:
                raise OrderNotFound(str(order_id))
            if order.status is OrderStatus.PAID:
                return order
            if order.status in {OrderStatus.PENDING_PAYMENT, OrderStatus.PAYMENT_FAILED}:
                order.start_payment()
                await uow.orders.save(order)
                await uow.commit()
            elif order.status is not OrderStatus.PAYMENT_IN_PROGRESS:
                status_name = getattr(order.status, "name", str(order.status))
                raise InvalidOrderTransition(
                    f"cannot process payment from {status_name}"
                )

        try:
            result = await self._gateway.charge(
                order_id=order.id,
                total=order.total,
                idempotency_key=f"charge:{order.id}",
            )
        except PaymentDeclined:
            async with self._uow_factory() as uow:
                failed = await uow.orders.get(order_id)
                if failed is None:
                    raise OrderNotFound(str(order_id))
                failed.mark_payment_failed()
                await uow.orders.save(failed)
                await uow.commit()
                return failed
        except PaymentUncertain:
            raise

        async with self._uow_factory() as uow:
            paid = await uow.orders.get(order_id)
            if paid is None:
                raise OrderNotFound(str(order_id))
            paid.mark_paid(result.reference)
            await uow.orders.save(paid)
            await uow.commit()
            return paid
