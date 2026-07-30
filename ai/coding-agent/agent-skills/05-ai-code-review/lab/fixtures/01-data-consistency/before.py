class Ledger:
    def __init__(self, balances):
        self.balances = dict(balances)

    def balance(self, account_id):
        return self.balances[account_id]
