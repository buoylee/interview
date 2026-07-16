from pydantic import BaseModel, ConfigDict


class OrderRow:
    def __init__(self, order_id: str, status: str) -> None:
        self.order_id = order_id
        self.status = status


class OrderAttributeView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_id: str
    status: str


def test_from_attributes_only_projects_object_attributes() -> None:
    row = OrderRow("ord_0123456789ab", "pending_payment")
    view = OrderAttributeView.model_validate(row)
    assert view.model_dump() == {
        "order_id": "ord_0123456789ab",
        "status": "pending_payment",
    }
