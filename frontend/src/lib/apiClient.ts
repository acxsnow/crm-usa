import axios, { AxiosError, type AxiosInstance } from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

const TOKEN_STORAGE_KEY = "crm.tokens";

export interface TokenPair {
  access_token: string;
  refresh_token: string;
}

export function loadTokens(): TokenPair | null {
  const raw = localStorage.getItem(TOKEN_STORAGE_KEY);
  return raw ? (JSON.parse(raw) as TokenPair) : null;
}

export function saveTokens(tokens: TokenPair): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, JSON.stringify(tokens));
}

export function clearTokens(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

export const apiClient: AxiosInstance = axios.create({ baseURL: API_BASE_URL });

apiClient.interceptors.request.use((config) => {
  const tokens = loadTokens();
  if (tokens?.access_token) {
    config.headers.Authorization = `Bearer ${tokens.access_token}`;
  }
  return config;
});

let refreshPromise: Promise<TokenPair> | null = null;

async function refreshAccessToken(): Promise<TokenPair> {
  const tokens = loadTokens();
  if (!tokens?.refresh_token) throw new Error("No refresh token available.");
  const response = await axios.post<TokenPair>(`${API_BASE_URL}/auth/refresh`, {
    refresh_token: tokens.refresh_token,
  });
  saveTokens(response.data);
  return response.data;
}

// A 401 from these endpoints means "bad credentials / bad token", not "access
// token expired" — trying to refresh and then hard-redirecting to /login would
// wipe the page before the form can show its error message.
const AUTH_ENDPOINTS = ["/auth/login", "/auth/refresh", "/auth/logout"];

function isAuthEndpoint(url: string | undefined): boolean {
  return !!url && AUTH_ENDPOINTS.some((path) => url.includes(path));
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as (typeof error.config & { _retry?: boolean }) | undefined;
    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !isAuthEndpoint(originalRequest.url)
    ) {
      originalRequest._retry = true;
      try {
        refreshPromise ??= refreshAccessToken();
        const newTokens = await refreshPromise;
        refreshPromise = null;
        originalRequest.headers = originalRequest.headers ?? {};
        (originalRequest.headers as Record<string, string>).Authorization = `Bearer ${newTokens.access_token}`;
        return apiClient.request(originalRequest);
      } catch {
        refreshPromise = null;
        clearTokens();
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);
