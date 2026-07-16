import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from order_contracts.events.envelope import OrderCreatedEnvelopeV1, OrderCreatedEnvelopeV2
from order_contracts.inbound.create_order import CreateOrderRequest


SCHEMA_DIR = Path(__file__).parents[1] / "schemas"
MODELS: dict[str, type[BaseModel]] = {
    "create-order.schema.json": CreateOrderRequest,
    "order-created-v1.schema.json": OrderCreatedEnvelopeV1,
    "order-created-v2.schema.json": OrderCreatedEnvelopeV2,
}


@pytest.mark.parametrize(("filename", "model"), MODELS.items())
def test_json_schema_matches_reviewed_golden(filename: str, model: type[BaseModel]) -> None:
    expected = json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))
    assert model.model_json_schema(mode="validation") == expected
