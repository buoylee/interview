import json

from order_contracts.adapters import parse_create_order, to_create_order_command


RAW_REQUEST = json.dumps(
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
).encode()


def main() -> dict[str, str | int]:
    request = parse_create_order(RAW_REQUEST)
    command = to_create_order_command(request)
    return {"customer_id": command.customer_id, "line_count": len(command.lines)}


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False))
