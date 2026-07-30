class PaymentService:
    def __init__(self, gateway):
        self.gateway = gateway

    def charge(self, amount_cents):
        return self.gateway.capture(amount_cents)
