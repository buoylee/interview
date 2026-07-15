import json
import os
from pathlib import Path
from unittest.mock import patch

from order_contracts.config import load_settings


EXAMPLE_ENV = Path(__file__).parents[1] / ".env.example"


def main() -> dict[str, str]:
    with patch.dict(os.environ, {}, clear=True):
        settings = load_settings(env_file=EXAMPLE_ENV)
    return {
        "environment": settings.environment,
        "payment_base_url": str(settings.payment.base_url),
        "webhook_secret": str(settings.payment.webhook_secret),
    }


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False))
