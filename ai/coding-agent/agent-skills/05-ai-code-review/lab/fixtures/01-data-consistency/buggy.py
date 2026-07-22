class AccountNotFound(LookupError):
    pass


class InsufficientFunds(ValueError):
    pass


class Ledger:
    def __init__(self, balances):
        self.balances = dict(balances)

    def balance(self, account_id):
        return self.balances[account_id]

    def transfer(self, source_id, target_id, amount):
        if amount <= 0:
            raise ValueError("amount must be positive")
        if source_id not in self.balances:
            raise AccountNotFound(source_id)
        if self.balances[source_id] < amount:
            raise InsufficientFunds(source_id)

        self.balances[source_id] -= amount
        if target_id not in self.balances:
            raise AccountNotFound(target_id)
        self.balances[target_id] += amount
