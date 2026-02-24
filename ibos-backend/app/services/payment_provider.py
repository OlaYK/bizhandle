import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PaymentInitRequest:
    business_id: str
    checkout_session_id: str
    checkout_session_token: str
    amount: float
    currency: str
    success_redirect_url: str | None
    cancel_redirect_url: str | None


@dataclass(frozen=True)
class PaymentInitResult:
    provider: str
    payment_reference: str
    checkout_url: str | None = None


class PaymentProvider(Protocol):
    name: str

    def initialize_checkout(self, request: PaymentInitRequest) -> PaymentInitResult:
        ...


class StubPaymentProvider:
    name = "stub"

    def initialize_checkout(self, request: PaymentInitRequest) -> PaymentInitResult:
        reference = f"stub-{uuid.uuid4().hex[:18]}"
        checkout_url = request.success_redirect_url
        return PaymentInitResult(
            provider=self.name,
            payment_reference=reference,
            checkout_url=checkout_url,
        )


_PAYMENT_PROVIDERS: dict[str, PaymentProvider] = {
    "stub": StubPaymentProvider(),
}


def get_payment_provider(name: str) -> PaymentProvider:
    normalized = (name or "").strip().lower()
    provider = _PAYMENT_PROVIDERS.get(normalized)
    if not provider:
        available = ", ".join(sorted(_PAYMENT_PROVIDERS.keys()))
        raise ValueError(f"Unknown payment provider '{name}'. Available: {available}")
    return provider
