import json

from examples.consume_event import main as consume_event
from examples.fastapi_adapter import app, create_order, request_validation_handler
from examples.load_settings import main as load_settings
from examples.validate_http_payload import main as validate_http_payload
from fastapi.exceptions import RequestValidationError
from order_contracts.errors import ErrorResponse
from order_contracts.inbound.create_order import CreateOrderRequest
from order_contracts.outbound.views import CustomerOrderView
from starlette.requests import Request


def test_http_example_executes() -> None:
    assert validate_http_payload() == {
        "customer_id": "cus_0123456789ab",
        "line_count": 1,
    }


def test_event_example_executes() -> None:
    assert consume_event() == {
        "version": 2,
        "order_id": "ord_0123456789ab",
    }


def test_settings_example_never_returns_raw_secret() -> None:
    result = load_settings()
    assert result["environment"] == "development"
    assert result["webhook_secret"] == "**********"
    assert "replace-with-local-demo-secret" not in str(result)


def test_fastapi_adapter_registers_route_and_function_is_callable() -> None:
    assert any(route.path == "/orders" for route in app.routes)
    request = CreateOrderRequest.model_validate(
        {
            "customer_id": "cus_0123456789ab",
            "idempotency_key": "checkout-2026-0001",
            "items": [
                {
                    "sku": "SKU-RED-1",
                    "quantity": 2,
                    "unit_price": {"amount": "12.30", "currency": "USD"},
                }
            ],
        }
    )
    response = create_order(request)
    assert isinstance(response, CustomerOrderView)
    assert response.order_id == "ord_0123456789ab"


def test_fastapi_openapi_declares_contract_response_schema() -> None:
    responses = app.openapi()["paths"]["/orders"]["post"]["responses"]
    success_schema = responses["200"]["content"]["application/json"]["schema"]
    error_schema = responses["422"]["content"]["application/json"]["schema"]
    assert success_schema == {"$ref": "#/components/schemas/CustomerOrderView"}
    assert error_schema == {"$ref": "#/components/schemas/ErrorResponse"}


def test_fastapi_validation_handler_returns_safe_error_response() -> None:
    error = RequestValidationError(
        [
            {
                "type": "string_pattern_mismatch",
                "loc": ("body", "customer_id"),
                "msg": "String should match pattern",
                "input": "top-secret-customer-value",
            }
        ]
    )
    request = Request({"type": "http", "method": "POST", "path": "/orders"})

    response = request_validation_handler(request, error)

    body = response.body.decode()
    parsed = ErrorResponse.model_validate(json.loads(body))
    assert response.status_code == 422
    assert parsed.details[0].path == ["body", "customer_id"]
    assert "top-secret-customer-value" not in body
