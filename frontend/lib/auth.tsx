"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";
import { api, setAccessToken, setAuthExpiredHandler } from "./api";
import type { Organization, User } from "./types";

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthState {
  status: AuthStatus;
  token: string | null;
  user: User | null;
  organization: Organization | null;
  roles: string[];
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string, mfaCode?: string) => Promise<void>;
  logout: () => Promise<void>;
  hasRole: (...roles: string[]) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

async function establishSession(token: string) {
  setAccessToken(token);
  const me = await api.me();
  return { token, user: me.user, organization: me.organization, roles: me.roles };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    status: "loading",
    token: null,
    user: null,
    organization: null,
    roles: [],
  });

  useEffect(() => {
    setAuthExpiredHandler(() => {
      setAccessToken(null);
      setState({ status: "unauthenticated", token: null, user: null, organization: null, roles: [] });
    });

    api
      .refresh()
      .then((auth) => establishSession(auth.access_token))
      .then((session) =>
        setState({ status: "authenticated", token: session.token, user: session.user, organization: session.organization, roles: session.roles }),
      )
      .catch(() => {
        setAccessToken(null);
        setState({ status: "unauthenticated", token: null, user: null, organization: null, roles: [] });
      });
  }, []);

  const login = useCallback(async (email: string, password: string, mfaCode?: string) => {
    const auth = await api.login(email, password, mfaCode);
    const session = await establishSession(auth.access_token);
    setState({ status: "authenticated", token: session.token, user: session.user, organization: session.organization, roles: session.roles });
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // ignore logout errors; clear the session regardless
    }
    setAccessToken(null);
    setState({ status: "unauthenticated", token: null, user: null, organization: null, roles: [] });
  }, []);

  const hasRole = useCallback(
    (...roles: string[]) => state.roles.some((r) => roles.includes(r)),
    [state.roles],
  );

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, login, logout, hasRole }),
    [state, login, logout, hasRole],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
