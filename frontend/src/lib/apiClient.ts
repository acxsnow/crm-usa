import axios, { AxiosError, type AxiosInstance } from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

/**
 * Sesión (SEG-04). El refresh token, que dura días, vive en una cookie
 * HttpOnly que JavaScript no puede leer: el navegador la manda sola a
 * `/auth/*`. El access token (15 min) se guarda solo en memoria de esta
 * pestaña, nunca en localStorage, así que un script malicioso no puede
 * llevarse la sesión. Al recargar o abrir otra pestaña se renueva con la cookie.
 *
 * Sin señal (parques de casas móviles) la renovación falla por red, no porque
 * la sesión sea inválida: en ese caso NO se cierra la sesión. Solo un 401 del
 * servidor manda al ingreso.
 */
let accessToken: string | null = null;

// Las versiones anteriores guardaban los dos tokens aquí; se borran.
try { localStorage.removeItem("crm.tokens"); } catch { /* almacenamiento bloqueado */ }

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

/** ¿El servidor dijo que la sesión ya no vale? (y no un fallo de red). */
export function isSessionRejected(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 401;
}

export const apiClient: AxiosInstance = axios.create({ baseURL: API_BASE_URL, withCredentials: true });

apiClient.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

let refreshPromise: Promise<string> | null = null;

async function pedirAccessToken(): Promise<string> {
  const response = await axios.post<{ access_token: string }>(`${API_BASE_URL}/auth/refresh`, null, { withCredentials: true });
  accessToken = response.data.access_token;
  return accessToken;
}

/**
 * Pide un access token nuevo con la cookie. Cada renovación rota la cookie e
 * invalida la anterior, así que dos pestañas renovando a la vez se pisarían
 * (la segunda mandaría la cookie ya invalidada y cerraría la sesión). El
 * candado del navegador las pone en fila: la segunda sale con la cookie nueva.
 */
export function refreshAccessToken(): Promise<string> {
  refreshPromise ??= (navigator.locks ? conCandado() : pedirAccessToken()).finally(() => { refreshPromise = null; });
  return refreshPromise;
}

async function conCandado(): Promise<string> {
  let token = "";
  await navigator.locks.request("crm-auth-refresh", async () => { token = await pedirAccessToken(); });
  return token;
}

// A 401 from these endpoints means "bad credentials / bad token", not "access
// token expired" — trying to refresh and then hard-redirecting to /login would
// wipe the page before the form can show its error message.
const AUTH_ENDPOINTS = ["/auth/login", "/auth/refresh", "/auth/logout"];

function isAuthEndpoint(url: string | undefined): boolean {
  return !!url && AUTH_ENDPOINTS.some((path) => url.includes(path));
}

/** Lo llama el AuthContext para limpiar su estado cuando la sesión muere. */
let onSessionExpired: () => void = () => { window.location.href = "/login"; };
export function setOnSessionExpired(fn: () => void): void {
  onSessionExpired = fn;
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
        const nuevo = await refreshAccessToken();
        originalRequest.headers = originalRequest.headers ?? {};
        (originalRequest.headers as Record<string, string>).Authorization = `Bearer ${nuevo}`;
        return apiClient.request(originalRequest);
      } catch (refreshError) {
        if (isSessionRejected(refreshError)) {
          accessToken = null;
          onSessionExpired();
        }
        // Fallo de red: se devuelve el error y la sesión sigue para cuando vuelva la señal.
      }
    }
    return Promise.reject(error);
  }
);
