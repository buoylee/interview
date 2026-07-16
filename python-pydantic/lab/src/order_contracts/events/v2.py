from typing import Annotated

from pydantic import ConfigDict, Field, StrictInt

from order_contracts.events.v1 import OrderCreatedV1


class OrderCreatedV2(OrderCreatedV1):
    model_config = ConfigDict(extra="forbid", frozen=True)

    item_count: Annotated[StrictInt, Field(ge=1, le=100)]
