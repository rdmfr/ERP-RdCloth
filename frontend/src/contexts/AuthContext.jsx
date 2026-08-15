import { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("rdcloth_token");
    if (!token) { setLoading(false); return; }
    api.get("/auth/me")
      .then((r) => setUser(r.data))
      .catch(() => localStorage.removeItem("rdcloth_token"))
      .finally(() => setLoading(false));
  }, []);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.setItem("rdcloth_token", data.token);
    setUser(data.user);
    return data.user;
  };

  const logout = async () => {
    try { await api.post("/auth/logout"); } catch (e) { /* noop */ }
    localStorage.removeItem("rdcloth_token");
    setUser(null);
    window.location.href = "/login";
  };

  const canAccess = (module) => {
    if (!user) return false;
    const map = {
      owner: ["*"],
      admin: ["sales","orders","products","inventory","customers","suppliers","dashboard","materials"],
      production: ["production","inventory","products","materials","dashboard"],
      finance: ["finance","reports","purchasing","sales","dashboard","expenses","assets"],
    };
    const list = map[user.role] || [];
    return list.includes("*") || list.includes(module);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, canAccess }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
