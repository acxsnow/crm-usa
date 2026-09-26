import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { apiClient, clearTokens, loadTokens, saveTokens } from "@/lib/apiClient";
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

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchCurrentUser = useCallback(async () => {
    try {
      const response = await apiClient.get<CurrentUser>("/auth/me");
      setUser(response.data);
    } catch {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    const tokens = loadTokens();
    if (!tokens) {
      setIsLoading(false);
      return;
    }
    fetchCurrentUser().finally(() => setIsLoading(false));
  }, [fetchCurrentUser]);

  const login = useCallback(
    async (email: string, password: string) => {
      const response = await apiClient.post("/auth/login", { email, password });
      saveTokens(response.data);
      await fetchCurrentUser();
    },
    [fetchCurrentUser]
  );

  const logout = useCallback(async () => {
    const tokens = loadTokens();
    if (tokens?.refresh_token) {
      try {
        await apiClient.post("/auth/logout", { refresh_token: tokens.refresh_token });
      } catch {
        // best-effort; proceed with local logout regardless
      }
    }
    clearTokens();
    setUser(null);
  }, []);

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
