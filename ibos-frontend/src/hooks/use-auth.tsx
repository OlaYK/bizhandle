import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type PropsWithChildren
} from "react";
import { clearSession, getSessionTokens, persistSession, type SessionTokens } from "../api/auth-storage";
import type { TokenOut } from "../api/types";

interface AuthContextValue {
  tokens: SessionTokens | null;
  isAuthenticated: boolean;
  setSession: (tokenOut: TokenOut) => void;
  clearAuth: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: PropsWithChildren) {
  const [tokens, setTokens] = useState<SessionTokens | null>(() => getSessionTokens());

  const setSession = useCallback((tokenOut: TokenOut) => {
    persistSession(tokenOut);
    setTokens({
      accessToken: tokenOut.access_token,
      refreshToken: tokenOut.refresh_token
    });
  }, []);

  const clearAuth = useCallback(() => {
    clearSession();
    setTokens(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      tokens,
      isAuthenticated: Boolean(tokens?.accessToken),
      setSession,
      clearAuth
    }),
    [tokens, setSession, clearAuth]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
