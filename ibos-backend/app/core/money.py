from decimal import Decimal, ROUND_HALF_UP

MONEY_QUANT = Decimal("0.01")
ZERO_MONEY = Decimal("0.00")


def to_money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
