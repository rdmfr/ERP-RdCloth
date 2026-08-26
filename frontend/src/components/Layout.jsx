import { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { useTheme } from "@/contexts/ThemeContext";
import { api } from "@/lib/api";
import {
  LayoutDashboard, ShoppingCart, Package, Boxes, Truck, Users, Factory,
  Wallet, FileBarChart, Calculator, HardHat, Settings, Sun, Moon,
  LogOut, Menu, X, Search, Bell, ClipboardList, TrendingUp, Layers, Upload,
} from "lucide-react";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, module: "dashboard" },
  { to: "/sales", label: "Sales", icon: ShoppingCart, module: "sales" },
  { to: "/marketplace-import", label: "Import Orders", icon: Upload, module: "sales" },
  { to: "/products", label: "Products", icon: Package, module: "products" },
  { to: "/materials", label: "Materials", icon: Layers, module: "materials" },
  { to: "/inventory", label: "Inventory", icon: Boxes, module: "inventory" },
  { to: "/purchasing", label: "Purchasing", icon: Truck, module: "purchasing" },
  { to: "/production", label: "Production", icon: Factory, module: "production" },
  { to: "/suppliers", label: "Suppliers", icon: HardHat, module: "suppliers" },
  { to: "/customers", label: "Customers", icon: Users, module: "customers" },
  { to: "/finance", label: "Finance", icon: Wallet, module: "finance" },
  { to: "/reports", label: "Reports", icon: FileBarChart, module: "reports" },
  { to: "/pricing", label: "Pricing / HPP", icon: Calculator, module: "dashboard" },
  { to: "/assets", label: "Assets", icon: ClipboardList, module: "assets" },
  { to: "/bep", label: "BEP", icon: TrendingUp, module: "dashboard" },
  { to: "/settings", label: "Settings", icon: Settings, module: "dashboard" },
];

export default function Layout({ children }) {
  const { user, logout, canAccess } = useAuth();
  const { theme, toggle } = useTheme();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [showNotifications, setShowNotifications] = useState(false);
  const nav = useNavigate();

  const items = NAV.filter((n) => canAccess(n.module));

  useEffect(() => {
    if (search.trim().length < 2) { setSearchResults([]); return; }
    const timer = setTimeout(() => api.get(`/search?q=${encodeURIComponent(search)}`).then(r => setSearchResults(r.data)).catch(() => setSearchResults([])), 250);
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => { api.get("/notifications").then(r => setNotifications(r.data.items || [])).catch(() => {}); }, []);

  return (
    <div className="min-h-screen flex bg-background text-foreground">
      {/* Sidebar */}
      <aside
        data-testid="sidebar"
        className={`fixed lg:sticky top-0 h-screen z-40 w-64 border-r border-border bg-stone-100 dark:bg-stone-900 transition-transform ${open ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}`}
      >
        <div className="flex items-center justify-between px-6 h-16 border-b border-border">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-md bg-neutral-900 dark:bg-stone-100 flex items-center justify-center text-white dark:text-stone-900 font-black text-sm font-display">Rd</div>
            <div>
              <div className="font-display font-bold text-sm tracking-tight">RdCloth</div>
              <div className="text-[10px] uppercase tracking-widest text-muted-foreground">ERP · Demo</div>
            </div>
          </div>
          <button className="lg:hidden" onClick={() => setOpen(false)} data-testid="sidebar-close"><X size={18}/></button>
        </div>
        <nav className="p-3 space-y-0.5 overflow-y-auto scroll-thin h-[calc(100vh-8rem)]">
          {items.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to} to={to} end={to === "/"}
              data-testid={`nav-${label.toLowerCase().replace(/[^a-z]/g,'-')}`}
              onClick={() => setOpen(false)}
              className={({isActive}) =>
                `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${isActive ? "bg-neutral-900 text-white dark:bg-stone-100 dark:text-stone-900" : "text-neutral-700 dark:text-stone-300 hover:bg-stone-200 dark:hover:bg-stone-800"}`
              }
            >
              <Icon size={16} strokeWidth={1.75} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="absolute bottom-0 left-0 right-0 border-t border-border p-3 bg-stone-100 dark:bg-stone-900">
          <button onClick={logout} data-testid="btn-logout" className="w-full flex items-center gap-2 px-3 py-2 text-sm rounded-md hover:bg-stone-200 dark:hover:bg-stone-800 text-neutral-700 dark:text-stone-300">
            <LogOut size={16} strokeWidth={1.75} /> Keluar
          </button>
        </div>
      </aside>

      {open && <div className="fixed inset-0 bg-black/40 z-30 lg:hidden" onClick={() => setOpen(false)} />}

      <div className="flex-1 min-w-0 flex flex-col">
        {/* Topbar */}
        <header className="sticky top-0 z-20 h-16 backdrop-blur-xl bg-white/70 dark:bg-stone-950/70 border-b border-border flex items-center px-4 lg:px-8 gap-4">
          <button className="lg:hidden" onClick={() => setOpen(true)} data-testid="sidebar-open"><Menu size={20}/></button>
          <div className="flex-1 max-w-md relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              data-testid="topbar-search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Cari produk, order, customer..."
              className="w-full pl-9 pr-3 py-2 bg-stone-100 dark:bg-stone-900 border border-border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-neutral-900 dark:focus:ring-stone-100"
            />
            {searchResults.length > 0 && <div className="absolute top-full left-0 right-0 mt-1 z-30 rounded-md border border-border bg-card shadow-lg overflow-hidden">
              {searchResults.map((result) => <button key={`${result.type}-${result.id}`} onClick={() => { setSearch(""); setSearchResults([]); }} className="block w-full text-left px-3 py-2 hover:bg-stone-100 dark:hover:bg-stone-900"><div className="text-sm font-semibold">{result.label}</div><div className="text-xs text-muted-foreground">{result.type} · {result.detail}</div></button>)}
            </div>}
          </div>
          <button onClick={toggle} data-testid="theme-toggle" className="p-2 rounded-md hover:bg-stone-100 dark:hover:bg-stone-900">
            {theme === "dark" ? <Sun size={16}/> : <Moon size={16}/>}
          </button>
          <button onClick={() => setShowNotifications((value) => !value)} className="p-2 rounded-md hover:bg-stone-100 dark:hover:bg-stone-900 relative" data-testid="notifications">
            <Bell size={16}/>
            {notifications.length > 0 && <span className="absolute -top-0.5 -right-0.5 min-w-4 h-4 px-1 rounded-full bg-rose-600 text-white text-[9px] leading-4">{notifications.length}</span>}
          </button>
          {showNotifications && <div className="absolute right-4 lg:right-8 top-14 z-30 w-80 rounded-md border border-border bg-card shadow-lg p-3"><div className="font-semibold text-sm mb-2">Notifications</div>{notifications.length === 0 ? <div className="text-sm text-muted-foreground">Tidak ada notifikasi.</div> : notifications.map((item, index) => <div key={index} className="py-2 border-t border-border text-sm"><span className="font-semibold">{item.severity}</span> · {item.message}</div>)}</div>}
          <div className="flex items-center gap-2" data-testid="user-profile">
            <div className="w-8 h-8 rounded-full bg-neutral-900 dark:bg-stone-100 text-white dark:text-stone-900 flex items-center justify-center text-xs font-bold font-display">
              {user?.name?.[0] || "U"}
            </div>
            <div className="hidden md:block leading-tight">
              <div className="text-sm font-semibold">{user?.name}</div>
              <div className="text-[10px] uppercase tracking-widest text-muted-foreground">{user?.role}</div>
            </div>
          </div>
        </header>

        <main className="flex-1 p-4 lg:p-8 min-w-0">{children}</main>
      </div>
    </div>
  );
}
