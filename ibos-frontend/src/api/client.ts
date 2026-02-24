import axios, { type AxiosRequestConfig, type InternalAxiosRequestConfig } from "axios";
import { endpoints } from "./endpoints";
import { clearSession, getSessionTokens, persistSession } from "./auth-storage";
import type { TokenOut } from "./types";

const baseURL = import.meta.env.VITE_API_BASE_URL;

if (!baseURL) {
  throw new Error("VITE_API_BASE_URL is not configured");
}

const AUTH_PATHS = new Set<string>([
  endpoints.auth.login,
  endpoints.auth.register,
  endpoints.auth.registerWithInvite,
  endpoints.auth.token,
  endpoints.auth.refresh,
  endpoints.auth.google
]);

function isAuthPath(url?: string) {
  if (!url) return false;
  return [...AUTH_PATHS].some((path) => url.includes(path));
}

type RetryableRequestConfig = InternalAxiosRequestConfig & {
  _retry?: boolean;
};

let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken() {
  const tokens = getSessionTokens();
  if (!tokens?.refreshToken) {
    return null;
  }

  const response = await axios.post<TokenOut>(
    `${baseURL}${endpoints.auth.refresh}`,
    { refresh_token: tokens.refreshToken },
    { timeout: 15000 }
  );

  persistSession(response.data);
  return response.data.access_token;
}

function redirectToLogin() {
  clearSession();
  if (window.location.pathname !== "/login" && window.location.pathname !== "/register") {
    window.location.assign("/login");
  }
}

export const apiClient = axios.create({
  baseURL,
  timeout: 15000
});

apiClient.interceptors.request.use((config) => {
  const tokens = getSessionTokens();
  if (tokens?.accessToken && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${tokens.accessToken}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error?.response?.status;
    const originalRequest = error?.config as RetryableRequestConfig | undefined;
    const requestUrl: string | undefined = originalRequest?.url;

    if (
      status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !isAuthPath(requestUrl)
    ) {
      originalRequest._retry = true;

      try {
        if (!refreshPromise) {
          refreshPromise = refreshAccessToken().finally(() => {
            refreshPromise = null;
          });
        }

        const newAccessToken = await refreshPromise;
        if (!newAccessToken) {
          redirectToLogin();
          return Promise.reject(error);
        }

        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        return apiClient(originalRequest as AxiosRequestConfig);
      } catch (refreshError) {
        redirectToLogin();
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);
