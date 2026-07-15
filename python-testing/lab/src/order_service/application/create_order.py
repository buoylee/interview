"""Order creation use case."""

from order_service.application.messages import CreateOrderCommand, OutboxMessage
from order_service.domain.order import Money, Order
from order_service.ports.system import Clock, IdGenerator
from order_service.ports.uow import UnitOfWorkFactory


class CreateOrder:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        ids: IdGenerator,
        clock: Clock,
    ) -> None:
        self._uow_factory = uow_factory
        self._ids = ids
        self._clock = clock

    async def execute(self, command: CreateOrderCommand) -> Order:
        async with self._uow_factory() as uow:
            existing = await uow.orders.get_by_idempotency_key(
                command.idempotency_key
            )
            if existing is not None:
                await uow.commit()
                return existing

            now = self._clock.now()
            order = Order.create(
                order_id=self._ids.new(),
                idempotency_key=command.idempotency_key,
                total=Money(command.amount, command.currency),
                created_at=now,
            )
            await uow.orders.add(order)
            await uow.outbox.add(
                OutboxMessage(
                    id=self._ids.new(),
                    topic="payment_requested",
                    aggregate_id=order.id,
                    payload={"order_id": str(order.id)},
                    occurred_at=now,
                    available_at=now,
                )
            )
            await uow.commit()
            return order
