from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.requests import Request

from order_contracts.adapters import project_customer_order, to_create_order_command
from order_contracts.domain.order import Order
from order_contracts.errors import ErrorDetail, ErrorResponse
from order_contracts.inbound.create_order import CreateOrderRequest
from order_contracts.outbound.views import CustomerOrderView


app = FastAPI(title="Order contract adapter")


@app.exception_handler(RequestValidationError)
def request_validation_handler(
    _request: Request,
    error: RequestValidationError,
) -> JSONResponse:
    response = ErrorResponse(
        details=[
            ErrorDetail(reason=item["type"], path=list(item["loc"]))
            for item in error.errors()
        ]
    )
    return JSONResponse(status_code=422, content=response.model_dump(mode="json"))


@app.post(
    "/orders",
    response_model=CustomerOrderView,
    responses={422: {"model": ErrorResponse}},
)
def create_order(payload: CreateOrderRequest) -> CustomerOrderView:
    command = to_create_order_command(payload)
    order = Order.create("ord_0123456789ab", command)
    return project_customer_order(order)
