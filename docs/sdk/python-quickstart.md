# Python SDK Quickstart (Starter)

## 1. Install
```bash
pip install requests
```

## 2. Configure
Set environment variables:
- `MONIDESK_BASE_URL` (for example `http://localhost:8000`)
- `MONIDESK_API_KEY` (created from `/developer/api-keys`)

## 3. Run Starter
Use `docs/sdk/examples/python/public_api_smoke.py` to:
- fetch `GET /public/v1/me`
- fetch `GET /public/v1/orders`

## 4. Webhook Signature Verification
Verify incoming signature with:
- header format: `sha256=<digest>`
- digest algorithm: HMAC-SHA256 over raw body bytes
