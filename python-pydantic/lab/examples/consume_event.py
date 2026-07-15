import json

from order_contracts.events.envelope import parse_order_created


RAW_EVENT = json.dumps(
    {
        "event_id": "msg_0123456789ab",
        "event_type": "order.created",
        "schema_version": 2,
        "occurred_at": "2026-07-15T12:30:00Z",
        "payload": {
            "order_id": "ord_0123456789ab",
            "customer_id": "cus_0123456789ab",
            "total": {"amount": "24.60", "currency": "USD"},
            "item_count": 1,
        },
    }
).encode()


def main() -> dict[str, str | int]:
    event = parse_order_created(RAW_EVENT)
    return {"version": event.schema_version, "order_id": event.payload.order_id}


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False))
