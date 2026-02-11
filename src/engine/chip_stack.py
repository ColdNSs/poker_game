class ChipStack:
    def __init__(self, amount: int = 0):
        assert amount >= 0
        self._amount = amount

    def __repr__(self):
        return f"Stack of {self.amount}"

    @property
    def amount(self) -> int:
        return self._amount

    def pop(self, amount: int) -> int:
        if amount < 0:
            raise ValueError("Cannot remove negative chips")
        if amount > self._amount:
            raise ValueError(
                f"Stack has insufficient chips "
                f"({self._amount} < {amount})"
            )
        self._amount -= amount
        return amount

    def add(self, amount: int) -> None:
        if amount < 0:
            raise ValueError("Cannot add negative chips")
        self._amount += amount

