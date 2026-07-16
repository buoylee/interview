from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, status

from order_service.api.dependencies import get_create_order, get_legacy_refund
from order_service.api.schemas import (
    CreateOrderRequest,
    OrderResponse,
    RefundResponse,
)
from order_service.application.create_order import CreateOrder
from order_service.application.legacy_refund import (
    CapturedPaymentMissing,
    LegacyRefund,
)
from order_service.application.messages import CreateOrderCommand
from order_service.application.process_payment import OrderNotFound


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.ready = True
        try:
            yield
        finally:
            app.state.ready = False

    app = FastAPI(
        title="Order Service Testing Lab",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.post(
        "/orders",
        response_model=OrderResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_order(
        body: CreateOrderRequest,
        idempotency_key: Annotated[
            str,
            Header(
                alias="Idempotency-Key",
                min_length=1,
                pattern=r".*\S.*",
            ),
        ],
        use_case: Annotated[CreateOrder, Depends(get_create_order)],
    ) -> OrderResponse:
        order = await use_case.execute(
            CreateOrderCommand(idempotency_key, body.amount, body.currency)
        )
        return OrderResponse.from_domain(order)

    @app.post(
        "/orders/{order_id}/refunds",
        response_model=RefundResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def refund_order(
        order_id: UUID,
        use_case: Annotated[LegacyRefund, Depends(get_legacy_refund)],
        request_id: Annotated[
            str,
            Header(
                alias="Idempotency-Key",
                min_length=1,
                pattern=r".*\S.*",
            ),
        ],
    ) -> RefundResponse:
        try:
            await use_case.execute(order_id, request_id)
        except OrderNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="order not found",
            ) from exc
        except CapturedPaymentMissing as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="order has no captured payment",
            ) from exc
        return RefundResponse(order_id=order_id, status="accepted")

    return app
