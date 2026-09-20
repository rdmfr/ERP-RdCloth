import axios from "axios";
import { APP_CONFIG, getBusinessPreferences } from "@/config/appConfig";

// An empty backend URL means same-origin in production (Docker Nginx proxy),
// but automatically defaults to http://localhost:8000 during local development (port 3000).
const configuredBackendUrl = (process.env.REACT_APP_BACKEND_URL || "").trim();
const isDockerOrProd = typeof window !== "undefined" && (window.location.port === "80" || window.location.port === "443" || window.location.port === "");
const backendUrl = configuredBackendUrl || (isDockerOrProd ? window.location.origin : "http://localhost:8000");
const API = `${backendUrl.replace(/\/$/, "")}/api`;

export const api = axios.create({ baseURL: API, withCredentials: true });

api.interceptors.request.use((cfg) => {
  const token = localStorage.getItem("nexabiz_token");
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

api.interceptors.response.use(
  (r) => r,
  (e) => {
    if (e.response?.status === 401) {
      localStorage.removeItem("nexabiz_token");
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
