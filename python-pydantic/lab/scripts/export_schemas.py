import json
from pathlib import Path

from pydantic import BaseModel

from order_contracts.events.envelope import OrderCreatedEnvelopeV1, OrderCreatedEnvelopeV2
from order_contracts.inbound.create_order import CreateOrderRequest


ROOT = Path(__file__).parents[1]
SCHEMA_DIR = ROOT / "schemas"
MODELS: dict[str, type[BaseModel]] = {
    "create-order.schema.json": CreateOrderRequest,
    "order-created-v1.schema.json": OrderCreatedEnvelopeV1,
    "order-created-v2.schema.json": OrderCreatedEnvelopeV2,
}


def render_schema(model: type[BaseModel]) -> str:
    schema = model.model_json_schema(mode="validation")
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> None:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    for filename, model in MODELS.items():
        (SCHEMA_DIR / filename).write_text(render_schema(model), encoding="utf-8")


if __name__ == "__main__":
    main()
