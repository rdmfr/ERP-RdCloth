import { useEffect, useState } from "react";
import { api, fmtIDR, fmtNum } from "@/lib/api";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell, Legend } from "recharts";
import { TrendingUp, TrendingDown, DollarSign, ShoppingBag, Wallet, Boxes, AlertTriangle, Activity } from "lucide-react";

const PERIODS = [{k:"today",l:"Hari Ini"},{k:"week",l:"Minggu"},{k:"month",l:"Bulan"},{k:"year",l:"Tahun"}];
const COLORS = ["#059669","#0284c7","#d97706","#dc2626","#7c3aed","#0891b2"];

function KPI({ label, value, hint, icon: Icon, tone = "neutral", testid }) {
  const toneMap = { neutral: "", success: "text-emerald-600 dark:text-emerald-400", danger: "text-rose-600 dark:text-rose-400" };
  return (
    <div className="p-5 rounded-lg border border-border bg-card hover:-translate-y-[2px] transition-transform" data-testid={testid}>
      <div className="flex items-center justify-between mb-4">
        <div className="text-[10px] uppercase font-bold tracking-[0.2em] text-muted-foreground">{label}</div>
        <Icon size={16} strokeWidth={1.5} className="text-muted-foreground" />
      </div>
      <div className={`kpi-value text-3xl ${toneMap[tone]}`}>{value}</div>
      {hint && <div className="text-xs text-muted-foreground mt-2">{hint}</div>}
    </div>
  );
}

function HealthPill({ health }) {
  const map = {
    healthy: { l: "HEALTHY", c: "bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-400 dark:border-emerald-900/50" },
    warning: { l: "WARNING", c: "bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400 dark:border-amber-900/50" },
    critical: { l: "CRITICAL", c: "bg-rose-100 text-rose-800 border-rose-200 dark:bg-rose-900/30 dark:text-rose-400 dark:border-rose-900/50" },
  };
  const s = map[health] || map.healthy;
  return <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest border ${s.c}`} data-testid="health-pill"><span className="w-1.5 h-1.5 rounded-full bg-current"/>{s.l}</span>;
}

export default function Dashboard() {
  const [period, setPeriod] = useState("month");
  const [kpi, setKpi] = useState(null);
  const [charts, setCharts] = useState(null);

  useEffect(() => {
    api.get(`/dashboard/kpi?period=${period}`).then(r => setKpi(r.data));
    api.get(`/dashboard/charts`).then(r => setCharts(r.data));
  }, [period]);

  if (!kpi) return <div className="text-muted-foreground">Memuat dashboard...</div>;

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="text-[10px] uppercase font-bold tracking-[0.25em] text-muted-foreground mb-1">Owner Overview</div>
          <h1 className="font-display font-black text-3xl sm:text-4xl tracking-tighter">Dashboard</h1>
          <div className="mt-2 flex items-center gap-3">
            <HealthPill health={kpi.health} />
            <span className="text-sm text-muted-foreground">
              {kpi.health === "healthy" && "Bisnis Anda dalam kondisi sehat. Terus jaga margin & cashflow."}
              {kpi.health === "warning" && "Perhatikan margin — profit di bawah target."}
              {kpi.health === "critical" && "Kondisi kritis: cash rendah atau merugi."}
            </span>
          </div>
        </div>
        <div className="flex bg-stone-100 dark:bg-stone-900 rounded-md p-1" data-testid="period-selector">
          {PERIODS.map(p => (
            <button key={p.k} onClick={() => setPeriod(p.k)} data-testid={`period-${p.k}`}
              className={`px-3 py-1.5 text-xs font-semibold rounded transition-colors ${period===p.k?"bg-neutral-900 text-white dark:bg-stone-100 dark:text-stone-900":"text-muted-foreground hover:text-foreground"}`}>{p.l}</button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        <KPI label="Revenue" value={fmtIDR(kpi.revenue)} icon={DollarSign} testid="kpi-revenue" />
        <KPI label="Orders" value={fmtNum(kpi.total_orders)} icon={ShoppingBag} testid="kpi-orders" />
        <KPI label="COGS / HPP" value={fmtIDR(kpi.cogs)} icon={Activity} testid="kpi-cogs" />
        <KPI label="Gross Profit" value={fmtIDR(kpi.gross_profit)} icon={TrendingUp} tone="success" testid="kpi-gross-profit" />
        <KPI label="Marketplace Fees" value={fmtIDR(kpi.marketplace_fees)} icon={TrendingDown} testid="kpi-marketplace-fees" />
        <KPI label="Operating Exp." value={fmtIDR(kpi.operating_expenses)} icon={TrendingDown} testid="kpi-op-exp" />
        <KPI label="Net Profit" value={fmtIDR(kpi.net_profit)} icon={TrendingUp} tone={kpi.net_profit>=0?"success":"danger"} testid="kpi-net-profit" />
        <KPI label="Cash Balance" value={fmtIDR(kpi.cash_balance)} icon={Wallet} testid="kpi-cash" />
        <KPI label="Inventory Value" value={fmtIDR(kpi.inventory_value)} icon={Boxes} testid="kpi-inventory-value" />
        <KPI label="Low Stock" value={fmtNum(kpi.low_stock_count)} icon={AlertTriangle} tone={kpi.low_stock_count>0?"danger":"neutral"} testid="kpi-low-stock" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 p-5 rounded-lg border border-border bg-card">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-[10px] uppercase font-bold tracking-[0.2em] text-muted-foreground">Revenue & Profit</div>
              <h3 className="font-display font-bold text-lg tracking-tight">30 hari terakhir</h3>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={charts?.revenue_chart || []}>
              <XAxis dataKey="date" tick={{fontSize:11}} stroke="#94a3b8" />
              <YAxis tick={{fontSize:11}} stroke="#94a3b8" tickFormatter={(v)=>`${(v/1000).toFixed(0)}k`} />
              <Tooltip contentStyle={{background:"rgba(255,255,255,0.9)",border:"1px solid #e5e7eb",borderRadius:8,fontSize:12}} formatter={(v)=>fmtIDR(v)}/>
              <Legend wrapperStyle={{fontSize:11}}/>
              <Line type="monotone" dataKey="revenue" stroke="#0f172a" strokeWidth={2} dot={false} name="Revenue"/>
              <Line type="monotone" dataKey="profit" stroke="#059669" strokeWidth={2} dot={false} name="Net Profit"/>
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="p-5 rounded-lg border border-border bg-card">
          <div className="text-[10px] uppercase font-bold tracking-[0.2em] text-muted-foreground mb-1">Sales Channel</div>
          <h3 className="font-display font-bold text-lg tracking-tight mb-3">Distribusi Omzet</h3>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={charts?.channel_chart || []} dataKey="value" nameKey="channel" cx="50%" cy="50%" innerRadius={45} outerRadius={80} paddingAngle={2}>
                {(charts?.channel_chart || []).map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip formatter={(v)=>fmtIDR(v)} contentStyle={{fontSize:12,border:"1px solid #e5e7eb",borderRadius:8}}/>
              <Legend wrapperStyle={{fontSize:10}}/>
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="lg:col-span-2 p-5 rounded-lg border border-border bg-card">
          <div className="text-[10px] uppercase font-bold tracking-[0.2em] text-muted-foreground mb-1">Best Sellers</div>
          <h3 className="font-display font-bold text-lg tracking-tight mb-3">Produk Paling Laku</h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={charts?.top_products || []} layout="vertical" margin={{left:80}}>
              <XAxis type="number" tick={{fontSize:11}} tickFormatter={(v)=>`${(v/1000).toFixed(0)}k`}/>
              <YAxis type="category" dataKey="name" tick={{fontSize:11}} width={130}/>
              <Tooltip formatter={(v)=>fmtIDR(v)} contentStyle={{fontSize:12,border:"1px solid #e5e7eb",borderRadius:8}}/>
              <Bar dataKey="revenue" fill="#0f172a" radius={[0,4,4,0]}/>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="p-5 rounded-lg border border-border bg-card">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-[10px] uppercase font-bold tracking-[0.2em] text-muted-foreground">Alert</div>
              <h3 className="font-display font-bold text-lg tracking-tight">Stok Menipis</h3>
            </div>
            <AlertTriangle size={16} className="text-amber-600"/>
          </div>
          <div className="space-y-2 max-h-64 overflow-y-auto scroll-thin" data-testid="low-stock-list">
            {(kpi.low_stock_items || []).length === 0 && <div className="text-sm text-muted-foreground">Semua stok aman.</div>}
            {kpi.low_stock_items?.map((it, i) => (
              <div key={i} className="flex items-center justify-between p-2 rounded-md bg-amber-50 dark:bg-amber-900/20 border border-amber-200/60 dark:border-amber-900/30">
                <div>
                  <div className="text-sm font-semibold">{it.name}</div>
                  <div className="text-[10px] uppercase text-muted-foreground">{it.kind}</div>
                </div>
                <div className="text-sm font-bold text-amber-700 dark:text-amber-400">{fmtNum(it.stock)} left</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
