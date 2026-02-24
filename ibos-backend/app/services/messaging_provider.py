import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class MessageSendRequest:
    business_id: str
    recipient: str
    content: str


@dataclass(frozen=True)
class MessageSendResult:
    provider: str
    message_id: str
    status: str


class MessagingProvider(Protocol):
    name: str

    def send_message(self, request: MessageSendRequest) -> MessageSendResult:
        ...


class StubWhatsAppProvider:
    name = "whatsapp_stub"

    def send_message(self, request: MessageSendRequest) -> MessageSendResult:
        return MessageSendResult(
            provider=self.name,
            message_id=f"msg-{uuid.uuid4().hex[:14]}",
            status="sent",
        )


_MESSAGING_PROVIDERS: dict[str, MessagingProvider] = {
    "whatsapp_stub": StubWhatsAppProvider(),
}


def get_messaging_provider(name: str) -> MessagingProvider:
    normalized = (name or "").strip().lower()
    provider = _MESSAGING_PROVIDERS.get(normalized)
    if not provider:
        available = ", ".join(sorted(_MESSAGING_PROVIDERS))
        raise ValueError(f"Unknown messaging provider '{name}'. Available: {available}")
    return provider
