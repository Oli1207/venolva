import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, setAuthLostHandler, tokens } from "./api";

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  const logout = useCallback(() => {
    tokens.clear();
    setUser(null);
  }, []);

  useEffect(() => {
    setAuthLostHandler(logout);
    if (!tokens.get()) { setReady(true); return; }
    api.get("/auth/me/").then(setUser).catch(() => tokens.clear()).finally(() => setReady(true));
  }, [logout]);

  const login = useCallback((data) => {
    tokens.set({ access: data.access, refresh: data.refresh });
    setUser(data.user);
  }, []);

  const reload = useCallback(async () => {
    const me = await api.get("/auth/me/");
    setUser(me);
    return me;
  }, []);

  const value = useMemo(() => ({ user, ready, login, logout, reload, setUser }), [user, ready, login, logout, reload]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
