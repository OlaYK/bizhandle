import type { TokenOut } from "./types";

const ACCESS_TOKEN_KEY = "monidesk_access_token";
const REFRESH_TOKEN_KEY = "monidesk_refresh_token";

export interface SessionTokens {
  accessToken: string;
  refreshToken: string;
}

export function getSessionTokens(): SessionTokens | null {
  const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
  const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);

  if (!accessToken || !refreshToken) {
    return null;
  }

  return { accessToken, refreshToken };
}

export function persistSession(tokenOut: TokenOut) {
  localStorage.setItem(ACCESS_TOKEN_KEY, tokenOut.access_token);
  localStorage.setItem(REFRESH_TOKEN_KEY, tokenOut.refresh_token);
}

export function clearSession() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}
