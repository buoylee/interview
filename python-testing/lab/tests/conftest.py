import pytest

from tests.factories import OrderFactory, make_order

pytest_plugins = ["pytester"]


@pytest.fixture(scope="function")
def order_factory() -> OrderFactory:
    return make_order
