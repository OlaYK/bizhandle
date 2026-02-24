import os
import sys

import requests

base_url = os.getenv("MONIDESK_BASE_URL", "http://localhost:8000").rstrip("/")
api_key = os.getenv("MONIDESK_API_KEY")

if not api_key:
    raise RuntimeError("MONIDESK_API_KEY is required")

headers = {"X-Monidesk-Api-Key": api_key}


def main() -> int:
    me_response = requests.get(f"{base_url}/public/v1/me", headers=headers, timeout=15)
    me_response.raise_for_status()

    orders_response = requests.get(
        f"{base_url}/public/v1/orders",
        headers=headers,
        params={"limit": 5, "offset": 0},
        timeout=15,
    )
    orders_response.raise_for_status()

    me = me_response.json()
    orders = orders_response.json()
    print(f"Business: {me['business_name']}")
    print(f"Orders total: {orders['pagination']['total']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except requests.RequestException as exc:
        print(f"Public API probe failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
