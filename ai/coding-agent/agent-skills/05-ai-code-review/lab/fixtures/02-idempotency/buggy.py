class PaymentService:
    def __init__(self, gateway):
        self.gateway = gateway

    def charge(self, idempotency_key, amount_cents):
        return self.gateway.capture(amount_cents)
