import { useEffect, useState } from "react";
import { api, fmtIDR, fmtNum, formatErr } from "@/lib/api";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell, Legend } from "recharts";
import { TrendingUp, TrendingDown, DollarSign, ShoppingBag, Wallet, Boxes, AlertTriangle, Activity } from "lucide-react";
import { Modal, Field, Input, Select, Button } from "./_shared";
import { toast } from "sonner";

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
  const [cashflow, setCashflow] = useState(null);
  const [showQuickExpense, setShowQuickExpense] = useState(false);
  const [accounts, setAccounts] = useState([]);
  const [expenseCategories, setExpenseCategories] = useState([]);
  const [expenseForm, setExpenseForm] = useState({
    category: "operasional",
    description: "",
    amount: 0,
    date: new Date().toISOString().slice(0, 10),
    account_id: "",
  });

  useEffect(() => {
    api.get(`/dashboard/kpi?period=${period}`).then(r => setKpi(r.data));
    api.get(`/dashboard/charts`).then(r => setCharts(r.data));
    api.get("/dashboard/cashflow").then(r => setCashflow(r.data));
    api.get("/accounts").then(r => setAccounts(r.data));
    api.get("/expense_categories").then(r => setExpenseCategories(r.data));
  }, [period]);

  const submitQuickExpense = async () => {
    try {
      await api.post("/expenses", {
        ...expenseForm,
        amount: Number(expenseForm.amount || 0),
        account_id: expenseForm.account_id || accounts.find(a => a.is_default)?.id || "",
      });
      toast.success("Biaya cepat berhasil dicatat");
      setShowQuickExpense(false);
      setExpenseForm({
        category: "operasional",
        description: "",
        amount: 0,
        date: new Date().toISOString().slice(0, 10),
        account_id: accounts.find(a => a.is_default)?.id || "",
      });
      api.get("/dashboard/cashflow").then(r => setCashflow(r.data));
      api.get(`/dashboard/kpi?period=${period}`).then(r => setKpi(r.data));
    } catch (e) {
      toast.error(formatErr(e.response?.data?.detail));
    }
  };

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
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" onClick={() => setShowQuickExpense(true)}>Quick Expense</Button>
          <div className="flex bg-stone-100 dark:bg-stone-900 rounded-md p-1" data-testid="period-selector">
            {PERIODS.map(p => (
              <button key={p.k} onClick={() => setPeriod(p.k)} data-testid={`period-${p.k}`}
                className={`px-3 py-1.5 text-xs font-semibold rounded transition-colors ${period===p.k?"bg-neutral-900 text-white dark:bg-stone-100 dark:text-stone-900":"text-muted-foreground hover:text-foreground"}`}>{p.l}</button>
            ))}
          </div>
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
      {cashflow && <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KPI label="Cash In Today" value={fmtIDR(cashflow.cash_in)} icon={TrendingUp} tone="success" />
        <KPI label="Cash Out Today" value={fmtIDR(cashflow.cash_out)} icon={TrendingDown} tone="danger" />
        <KPI label="Net Cash Today" value={fmtIDR(cashflow.net)} icon={Wallet} tone={cashflow.net >= 0 ? "success" : "danger"} />
        <KPI label="All Account Balance" value={fmtIDR(cashflow.balance)} icon={Wallet} />
      </div>}

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

      {showQuickExpense && (
        <Modal open onClose={() => setShowQuickExpense(false)} title="Quick Expense">
          <div className="space-y-3">
            <Field label="Kategori">
              <Select value={expenseForm.category} onChange={(event) => setExpenseForm({ ...expenseForm, category: event.target.value })}>
                {(expenseCategories.length ? expenseCategories : [{ id: "operasional", name: "Operasional" }, { id: "marketing", name: "Marketing" }, { id: "sewa", name: "Sewa" }, { id: "gaji", name: "Gaji" }]).map((item) => (
                  <option key={item.id || item.name} value={item.id || item.name}>{item.name}</option>
                ))}
              </Select>
            </Field>
            <Field label="Deskripsi"><Input value={expenseForm.description} onChange={(event) => setExpenseForm({ ...expenseForm, description: event.target.value })} /></Field>
            <Field label="Jumlah"><Input type="number" value={expenseForm.amount} onChange={(event) => setExpenseForm({ ...expenseForm, amount: event.target.value })} /></Field>
            <Field label="Tanggal"><Input type="date" value={expenseForm.date} onChange={(event) => setExpenseForm({ ...expenseForm, date: event.target.value })} /></Field>
            <Field label="Akun">
              <Select value={expenseForm.account_id} onChange={(event) => setExpenseForm({ ...expenseForm, account_id: event.target.value })}>
                <option value="">-- Pilih akun --</option>
                {accounts.map((account) => (
                  <option key={account.id} value={account.id}>{account.name}</option>
                ))}
              </Select>
            </Field>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setShowQuickExpense(false)}>Batal</Button>
              <Button onClick={submitQuickExpense}>Simpan</Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
