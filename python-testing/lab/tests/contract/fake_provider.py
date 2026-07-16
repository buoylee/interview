from uuid import UUID

import httpx
from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ChargeRequest(BaseModel):
    order_id: UUID
    amount: str
    currency: str


class RefundRequest(BaseModel):
    payment_reference: str
    amount: str
    currency: str


def create_fake_provider(*, refund_uncertain_once: bool = False) -> FastAPI:
    app = FastAPI()
    app.state.refund_attempts = []
    app.state.refund_operations = []
    app.state.refund_results = {}
    app.state.refund_uncertainty_remaining = int(refund_uncertain_once)

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
        attempt = {
            "payment_reference": body.payment_reference,
            "amount": body.amount,
            "currency": body.currency,
            "idempotency_key": idempotency_key,
        }
        app.state.refund_attempts.append(attempt)
        if idempotency_key in app.state.refund_results:
            stored = app.state.refund_results[idempotency_key]
            if stored["attempt"] != attempt:
                return JSONResponse(
                    status_code=409,
                    content={
                        "detail": (
                            "idempotency key reused with different refund body"
                        )
                    },
                )
            return stored["result"]
        result = {"status": "approved", "reference": "refund-001"}
        app.state.refund_operations.append(attempt)
        app.state.refund_results[idempotency_key] = {
            "attempt": attempt,
            "result": result,
        }
        if app.state.refund_uncertainty_remaining:
            app.state.refund_uncertainty_remaining -= 1
            raise httpx.ReadTimeout("refund response lost")
        return result

    return app
