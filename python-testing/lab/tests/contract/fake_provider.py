from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from uuid import UUID


class ChargeRequest(BaseModel):
    order_id: UUID
    amount: str
    currency: str


class RefundRequest(BaseModel):
    payment_reference: str
    amount: str
    currency: str


def create_fake_provider() -> FastAPI:
    app = FastAPI()

    @app.post("/charges")
    async def charge(
        body: ChargeRequest, idempotency_key: str = Header(alias="Idempotency-Key")
    ):
        assert body.currency == body.currency.upper()
        assert "." in body.amount
        if idempotency_key == "decline":
            return JSONResponse(
                status_code=402,
                content={"status": "declined", "reason": "insufficient_funds"},
            )
        if idempotency_key == "malformed":
            return {"status": "approved"}
        return {"status": "approved", "reference": "pay-001"}

    @app.post("/refunds")
    async def refund(
        body: RefundRequest, idempotency_key: str = Header(alias="Idempotency-Key")
    ):
        assert idempotency_key
        assert body.currency == body.currency.upper()
        return {"status": "approved", "reference": "refund-001"}

    return app
