import axios from "axios";
import { APP_CONFIG, getBusinessPreferences } from "@/config/appConfig";

const backendUrl = process.env.REACT_APP_BACKEND_URL || "http://localhost:8000";
const API = `${backendUrl}/api`;

export const api = axios.create({ baseURL: API });

api.interceptors.request.use((cfg) => {
  const token = localStorage.getItem("rdcloth_token");
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

api.interceptors.response.use(
  (r) => r,
  (e) => {
    if (e.response?.status === 401) {
      localStorage.removeItem("rdcloth_token");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(e);
  }
);

export const fmtIDR = (n) => {
  const { locale, currency } = getBusinessPreferences();
  return new Intl.NumberFormat(locale, { style: "currency", currency, maximumFractionDigits: 0 }).format(Number(n || 0));
};

export const fmtNum = (n) => new Intl.NumberFormat(getBusinessPreferences().locale).format(Number(n || 0));

export const fmtDate = (s) => {
  if (!s) return "-";
  try { return new Date(s).toLocaleDateString(getBusinessPreferences().locale, { day: "2-digit", month: "short", year: "numeric" }); }
  catch { return s; }
};

export function formatErr(detail) {
  if (!detail) return "Terjadi kesalahan";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((e) => e?.msg || JSON.stringify(e)).join(", ");
  if (typeof detail === "object" && detail.msg) return detail.msg;
  return String(detail);
}
