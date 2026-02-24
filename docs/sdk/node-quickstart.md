# Node SDK Quickstart (Starter)

## 1. Install
```bash
npm install axios
```

## 2. Configure
Set environment variables:
- `MONIDESK_BASE_URL` (for example `http://localhost:8000`)
- `MONIDESK_API_KEY` (created from `/developer/api-keys`)

## 3. Run Starter
Use `docs/sdk/examples/node/public-api-smoke.js` to:
- fetch `GET /public/v1/me`
- fetch `GET /public/v1/products`

## 4. Webhook Signature Verification
Use HMAC-SHA256 with your subscription signing secret against raw request body.
