import shortuuid


def generate_shortuuid() -> str:
    return shortuuid.uuid()


def generate_short_token(length: int = 12) -> str:
    return shortuuid.ShortUUID().random(length=length)
