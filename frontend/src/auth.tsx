import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { api, getToken, setToken, User } from "./api";

interface Ctx { user: User | null; loading: boolean; login: (token: string, u: User) => void; logout: () => void; refresh: () => Promise<void> }
const AuthCtx = createContext<Ctx>(null as unknown as Ctx);
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(!!getToken());
  const refresh = useCallback(async () => { try { setUser(await api<User>("/api/auth/me")); } catch { setUser(null); } setLoading(false); }, []);
  useEffect(() => { if (getToken()) refresh(); const h = () => setUser(null); window.addEventListener("cc-logout", h); return () => window.removeEventListener("cc-logout", h); }, [refresh]);
  const login = (t: string, u: User) => { setToken(t); setUser(u); };
  const logout = () => { setToken(null); setUser(null); };
  return <AuthCtx.Provider value={{ user, loading, login, logout, refresh }}>{children}</AuthCtx.Provider>;
}
