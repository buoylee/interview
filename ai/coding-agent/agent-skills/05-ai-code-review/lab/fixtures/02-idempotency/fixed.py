class IdempotencyConflict(ValueError):
    pass


class PaymentService:
    def __init__(self, gateway):
        self.gateway = gateway
        self._completed = {}

    def charge(self, idempotency_key, amount_cents):
        completed = self._completed.get(idempotency_key)
        if completed is not None:
            recorded_amount, receipt = completed
            if recorded_amount != amount_cents:
                raise IdempotencyConflict(idempotency_key)
            return receipt

        receipt = self.gateway.capture(amount_cents)
        self._completed[idempotency_key] = (amount_cents, receipt)
        return receipt
