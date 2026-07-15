import pytest

from order_service.domain.order import Order
from tests.factories import make_order


@pytest.fixture(scope="module")
def shared_order() -> Order:
    return make_order()
