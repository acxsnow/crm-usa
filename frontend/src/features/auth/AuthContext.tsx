import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { apiClient, isSessionRejected, refreshAccessToken, setAccessToken, setOnSessionExpired } from "@/lib/apiClient";
import type { CurrentUser } from "@/types/auth";

interface AuthContextValue {
  user: CurrentUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  hasPermission: (permissionCode: string) => boolean;
  /** ¿Tiene algún permiso de este módulo? Es lo que decide el menú y las rutas. */
  hasModule: (moduleKey: string) => boolean;
  refreshCurrentUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

// Perfil del usuario (nombre, roles, permisos) guardado para poder abrir la app
// sin señal con el menú correcto. No es una credencial: con esto no se llama a
// la API. Las credenciales están en la cookie HttpOnly y en memoria (SEG-04).
const PROFILE_KEY = "crm.profile";

function loadProfile(): CurrentUser | null {
  try {
    const raw = localStorage.getItem(PROFILE_KEY);
    return raw ? (JSON.parse(raw) as CurrentUser) : null;
  } catch {
    return null;
  }
}

function saveProfile(profile: CurrentUser | null): void {
  try {
    if (profile) localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
    else localStorage.removeItem(PROFILE_KEY);
  } catch {
    // almacenamiento bloqueado: la app sigue, solo que sin abrir sin señal
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const endSession = useCallback(() => {
    setAccessToken(null);
    saveProfile(null);
    setUser(null);
  }, []);

  const fetchCurrentUser = useCallback(async () => {
    try {
      const response = await apiClient.get<CurrentUser>("/auth/me");
      setUser(response.data);
      saveProfile(response.data);
    } catch (error) {
      // Sin señal se conserva el perfil guardado; solo un 401 cierra la sesión.
      if (isSessionRejected(error)) endSession();
      else setUser((actual) => actual ?? loadProfile());
    }
  }, [endSession]);

  useEffect(() => {
    setOnSessionExpired(() => {
      endSession();
      window.location.href = "/login";
    });
  }, [endSession]);

  // Al abrir la app: la cookie renueva la sesión. Si no hay red, se entra con el
  // perfil guardado y la sesión se renueva sola cuando vuelva la señal.
  useEffect(() => {
    refreshAccessToken()
      .then(() => fetchCurrentUser())
      .catch((error) => {
        if (isSessionRejected(error)) endSession();
        else setUser(loadProfile());
      })
      .finally(() => setIsLoading(false));
  }, [fetchCurrentUser, endSession]);

  const login = useCallback(
    async (email: string, password: string) => {
      const response = await apiClient.post<{ access_token: string }>("/auth/login", { email, password });
      setAccessToken(response.data.access_token);
      await fetchCurrentUser();
    },
    [fetchCurrentUser]
  );

  const logout = useCallback(async () => {
    try {
      await apiClient.post("/auth/logout");
    } catch {
      // best-effort; proceed with local logout regardless
    }
    endSession();
  }, [endSession]);

  const hasPermission = useCallback(
    (permissionCode: string) => user?.permissions.includes(permissionCode) ?? false,
    [user]
  );

  const hasModule = useCallback(
    (moduleKey: string) => user?.modules?.includes(moduleKey) ?? false,
    [user]
  );

  const value = useMemo(
    () => ({
      user,
      isLoading,
      isAuthenticated: Boolean(user),
      login,
      logout,
      hasPermission,
      hasModule,
      refreshCurrentUser: fetchCurrentUser,
    }),
    [user, isLoading, login, logout, hasPermission, hasModule, fetchCurrentUser]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within an AuthProvider.");
  return context;
}
