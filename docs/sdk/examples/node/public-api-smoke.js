const axios = require("axios");

const baseUrl = process.env.MONIDESK_BASE_URL || "http://localhost:8000";
const apiKey = process.env.MONIDESK_API_KEY;

if (!apiKey) {
  throw new Error("MONIDESK_API_KEY is required");
}

const client = axios.create({
  baseURL: baseUrl,
  timeout: 15000,
  headers: {
    "X-Monidesk-Api-Key": apiKey
  }
});

async function run() {
  const me = await client.get("/public/v1/me");
  const products = await client.get("/public/v1/products", { params: { limit: 5, offset: 0 } });

  console.log("Business:", me.data.business_name);
  console.log("Products total:", products.data.pagination.total);
}

run().catch((error) => {
  const message = error?.response?.data ?? error.message;
  console.error("Public API probe failed:", message);
  process.exitCode = 1;
});
