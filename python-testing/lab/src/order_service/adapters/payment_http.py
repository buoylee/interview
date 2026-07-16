from uuid import UUID

import httpx

from order_service.domain.order import Money
from order_service.ports.payment import (
    PaymentDeclined,
    PaymentProviderProtocolError,
    PaymentResult,
    PaymentUncertain,
)


class HTTPPaymentGateway:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def charge(
        self, *, order_id: UUID, total: Money, idempotency_key: str
    ) -> PaymentResult:
        try:
            response = await self._client.post(
                "/charges",
                headers={"Idempotency-Key": idempotency_key},
                json={
                    "order_id": str(order_id),
                    "amount": str(total.amount),
                    "currency": total.currency,
                },
            )
        except httpx.RequestError as exc:
            raise PaymentUncertain(str(exc)) from exc
        return self._map_response(response)

    async def refund(
        self, *, payment_reference: str, total: Money, idempotency_key: str
    ) -> PaymentResult:
        try:
            response = await self._client.post(
                "/refunds",
                headers={"Idempotency-Key": idempotency_key},
                json={
                    "payment_reference": payment_reference,
                    "amount": str(total.amount),
                    "currency": total.currency,
                },
            )
        except httpx.RequestError as exc:
            raise PaymentUncertain(str(exc)) from exc
        return self._map_response(response)

    @staticmethod
    def _map_response(response: httpx.Response) -> PaymentResult:
        if response.status_code == 402:
            reason = None
            try:
                body = response.json()
                if isinstance(body, dict):
                    reason = body.get("reason")
            except ValueError:
                pass
            raise PaymentDeclined(
                reason if isinstance(reason, str) and reason else "payment declined"
            )
        if response.status_code != 200:
            raise PaymentProviderProtocolError(
                f"provider returned status {response.status_code}"
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise PaymentProviderProtocolError("invalid provider response") from exc

        if not isinstance(body, dict):
            raise PaymentProviderProtocolError("invalid provider response")
        reference = body.get("reference")
        valid_reference = isinstance(reference, str) and bool(reference)
        if body.get("status") != "approved" or not valid_reference:
            raise PaymentProviderProtocolError("invalid provider response")
        assert isinstance(reference, str)
        return PaymentResult(reference)
