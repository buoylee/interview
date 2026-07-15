import json

import pytest

from order_contracts.performance import compare_json_validation


def test_performance_observation_has_no_machine_specific_threshold() -> None:
    raw = json.dumps(
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
    observation = compare_json_validation(raw, iterations=10)
    assert observation.iterations == 10
    assert observation.direct_json_seconds > 0
    assert observation.loads_then_validate_seconds > 0


def test_performance_observation_requires_positive_iterations() -> None:
    with pytest.raises(ValueError, match="iterations must be positive"):
        compare_json_validation(b"{}", iterations=0)
