from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, status

from order_service.api.dependencies import get_create_order
from order_service.api.schemas import CreateOrderRequest, OrderResponse
from order_service.application.create_order import CreateOrder
from order_service.application.messages import CreateOrderCommand


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

    return app
