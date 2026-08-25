import { useCallback, useState, useEffect } from "react";
import { PageHeader, Field, Input, Button } from "./_shared";
import { api, fmtIDR } from "@/lib/api";
import { downloadCSV, printPage } from "@/lib/export";
import { toast } from "sonner";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, Legend } from "recharts";
import { Download, Printer } from "lucide-react";

const HEALTH_CLR = { too_low:"bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-400", safe:"bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400", healthy:"bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400", premium:"bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400" };

export function HPPCalculator() {
  const [items, setItems] = useState([
    { label:"Blank T-Shirt", amount:30000 },
    { label:"DTF Transfer", amount:15000 },
    { label:"Packaging", amount:4000 },
    { label:"Sticker", amount:1500 },
    { label:"Hang Tag", amount:500 },
    { label:"Thank You Card", amount:500 },
    { label:"Electricity", amount:1000 },
    { label:"Reject Allowance", amount:2000 },
  ]);
  const [sp, setSp] = useState(89000);
  const [mpPct, setMpPct] = useState(10);
  const [ads, setAds] = useState(3000);
  const [disc, setDisc] = useState(0);
  const [result, setResult] = useState(null);

  const hpp = items.reduce((s,i)=>s+Number(i.amount||0),0);

  const calc = async () => {
    try {
      const { data } = await api.post("/hpp/calculate", { components: items, selling_price: Number(sp), marketplace_fee_pct: Number(mpPct), advertising: Number(ads), discount: Number(disc) });
      setResult(data);
    } catch (e) { toast.error("Gagal menghitung"); }
  };

  return (
    <div>
      <PageHeader title="HPP Calculator" subtitle="Hitung modal & harga jual"/>
      <div className="grid lg:grid-cols-2 gap-4">
        <div className="p-6 rounded-lg border border-border bg-card">
          <h3 className="font-display font-bold text-lg tracking-tight mb-4">Komponen HPP</h3>
          <div className="space-y-2 mb-4">
            {items.map((it,i)=>(
              <div key={i} className="grid grid-cols-[1fr_140px_auto] gap-2">
                <Input value={it.label} onChange={e=>setItems(items.map((x,idx)=>idx===i?{...x,label:e.target.value}:x))} />
                <Input type="number" value={it.amount} onChange={e=>setItems(items.map((x,idx)=>idx===i?{...x,amount:Number(e.target.value)}:x))} data-testid={`hpp-item-${i}`}/>
                <button onClick={()=>setItems(items.filter((_,x)=>x!==i))} className="text-rose-500">×</button>
              </div>
            ))}
          </div>
          <Button variant="outline" onClick={()=>setItems([...items,{label:"",amount:0}])}>+ Komponen</Button>

          <div className="mt-4 pt-4 border-t border-border">
            <div className="text-[10px] uppercase font-bold tracking-widest text-muted-foreground">Total HPP</div>
            <div className="kpi-value text-4xl" data-testid="hpp-total">{fmtIDR(hpp)}</div>
          </div>

          <h3 className="font-display font-bold text-lg tracking-tight mt-6 mb-3">Harga Jual & Fee</h3>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Selling Price"><Input type="number" value={sp} onChange={e=>setSp(e.target.value)} data-testid="hpp-sp"/></Field>
            <Field label="Marketplace Fee %"><Input type="number" value={mpPct} onChange={e=>setMpPct(e.target.value)}/></Field>
            <Field label="Advertising"><Input type="number" value={ads} onChange={e=>setAds(e.target.value)}/></Field>
            <Field label="Discount"><Input type="number" value={disc} onChange={e=>setDisc(e.target.value)}/></Field>
          </div>
          <Button onClick={calc} className="mt-4 w-full" data-testid="hpp-calc-btn">Hitung Profitabilitas</Button>
        </div>

        <div className="p-6 rounded-lg border border-border bg-card">
          <h3 className="font-display font-bold text-lg tracking-tight mb-4">Hasil Analisis</h3>
          {!result && <div className="text-sm text-muted-foreground py-16 text-center">Klik hitung untuk melihat hasil.</div>}
          {result && (
            <div className="space-y-3" data-testid="hpp-result">
              <Row label="HPP" value={fmtIDR(result.hpp)}/>
              <Row label="Selling Price" value={fmtIDR(result.selling_price)}/>
              <Row label="Marketplace Fee" value={fmtIDR(result.marketplace_fee)} tone="danger"/>
              <Row label="Gross Profit" value={fmtIDR(result.gross_profit)} tone="success"/>
              <Row label="Net Profit" value={fmtIDR(result.net_profit)} tone={result.net_profit>=0?"success":"danger"} big/>
              <div className="pt-3">
                <div className="text-[10px] uppercase font-bold tracking-widest text-muted-foreground">Net Margin</div>
                <div className="flex items-center gap-3 mt-1">
                  <div className="kpi-value text-3xl">{result.margin_percent}%</div>
                  <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest ${HEALTH_CLR[result.health]}`} data-testid="hpp-health">{result.health.replace("_"," ")}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, tone, big }) {
  const toneClr = tone==="success"?"text-emerald-600":tone==="danger"?"text-rose-600":"";
  return <div className="flex items-baseline justify-between border-b border-border pb-2"><span className="text-sm text-muted-foreground">{label}</span><span className={`font-display font-bold ${big?"text-2xl":"text-base"} ${toneClr}`}>{value}</span></div>;
}

export function PricingSimulator() {
  const [hpp, setHpp] = useState(54500);
  const [mpPct, setMpPct] = useState(10);
  const [ads, setAds] = useState(3000);
  const [prices, setPrices] = useState("69000,79000,89000,99000,109000,119000");
  const [result, setResult] = useState(null);

  const run = async () => {
    try {
      const { data } = await api.post("/hpp/simulate", { hpp:Number(hpp), marketplace_fee_pct:Number(mpPct), advertising:Number(ads), prices: prices.split(",").map(Number).filter(Boolean) });
      setResult(data.scenarios);
    } catch { toast.error("Gagal simulasi"); }
  };

  return (
    <div>
      <PageHeader title="Pricing Simulator" subtitle="Apakah harga jual saya sehat?"/>
      <div className="grid lg:grid-cols-[380px_1fr] gap-4">
        <div className="p-6 rounded-lg border border-border bg-card space-y-3 h-fit">
          <Field label="HPP"><Input type="number" value={hpp} onChange={e=>setHpp(e.target.value)} data-testid="sim-hpp"/></Field>
          <Field label="Marketplace Fee %"><Input type="number" value={mpPct} onChange={e=>setMpPct(e.target.value)}/></Field>
          <Field label="Advertising"><Input type="number" value={ads} onChange={e=>setAds(e.target.value)}/></Field>
          <Field label="Harga (koma-separated)"><Input value={prices} onChange={e=>setPrices(e.target.value)}/></Field>
          <Button onClick={run} className="w-full" data-testid="sim-run">Jalankan Simulasi</Button>
        </div>
        <div className="p-6 rounded-lg border border-border bg-card">
          {!result && <div className="text-sm text-muted-foreground text-center py-16">Klik jalankan simulasi.</div>}
          {result && (
            <>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={result}>
                  <XAxis dataKey="price" tick={{fontSize:11}} tickFormatter={(v)=>`${v/1000}k`}/>
                  <YAxis tick={{fontSize:11}} tickFormatter={(v)=>`${(v/1000).toFixed(0)}k`}/>
                  <Tooltip formatter={v=>fmtIDR(v)} contentStyle={{fontSize:12,border:"1px solid #e5e7eb",borderRadius:8}}/>
                  <Legend wrapperStyle={{fontSize:11}}/>
                  <ReferenceLine y={0} stroke="#000"/>
                  <Bar dataKey="profit" fill="#059669" name="Profit" radius={[4,4,0,0]}/>
                </BarChart>
              </ResponsiveContainer>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-sm" data-testid="sim-table">
                  <thead className="text-[10px] uppercase text-muted-foreground"><tr><th className="text-left p-2">Price</th><th className="text-right p-2">Profit</th><th className="text-right p-2">Margin</th><th className="text-right p-2">Health</th></tr></thead>
                  <tbody>
                  {result.map((r,i)=>(
                    <tr key={i} className="border-t border-border">
                      <td className="p-2 font-mono">{fmtIDR(r.price)}</td>
                      <td className="p-2 text-right font-semibold">{fmtIDR(r.profit)}</td>
                      <td className="p-2 text-right">{r.margin}%</td>
                      <td className="p-2 text-right"><span className={`inline-block px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-widest ${HEALTH_CLR[r.health]}`}>{r.health.replace("_"," ")}</span></td>
                    </tr>
                  ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export function BEPCalculator() {
  const [fc, setFc] = useState(1000000);
  const [vc, setVc] = useState(54500);
  const [sp, setSp] = useState(89000);
  const [res, setRes] = useState(null);
  const run = async () => {
    const { data } = await api.post("/bep/calculate", { fixed_cost:Number(fc), variable_cost:Number(vc), selling_price:Number(sp) });
    setRes(data);
  };

  const chartData = [];
  if (res) {
    for (let u=0; u<=res.bep_unit*2; u+=Math.max(1,Math.floor(res.bep_unit/10))) {
      chartData.push({ units:u, revenue:u*Number(sp), total_cost:Number(fc)+u*Number(vc), profit:u*Number(sp)-Number(fc)-u*Number(vc) });
    }
  }

  return (
    <div>
      <PageHeader title="Break Even Point" subtitle="Kapan bisnis balik modal?"/>
      <div className="grid lg:grid-cols-[380px_1fr] gap-4">
        <div className="p-6 rounded-lg border border-border bg-card space-y-3 h-fit">
          <Field label="Fixed Cost (bulan)"><Input type="number" value={fc} onChange={e=>setFc(e.target.value)} data-testid="bep-fc"/></Field>
          <Field label="Variable Cost / Unit"><Input type="number" value={vc} onChange={e=>setVc(e.target.value)}/></Field>
          <Field label="Selling Price"><Input type="number" value={sp} onChange={e=>setSp(e.target.value)}/></Field>
          <Button onClick={run} className="w-full" data-testid="bep-calc">Hitung BEP</Button>
          {res && (
            <div className="pt-3 border-t border-border space-y-2" data-testid="bep-result">
              <div><div className="text-[10px] uppercase font-bold tracking-widest text-muted-foreground">Contribution Margin</div><div className="font-bold">{fmtIDR(res.contribution_margin)}</div></div>
              <div><div className="text-[10px] uppercase font-bold tracking-widest text-muted-foreground">BEP Unit</div><div className="kpi-value text-2xl">{res.bep_unit.toFixed(0)} pcs</div></div>
              <div><div className="text-[10px] uppercase font-bold tracking-widest text-muted-foreground">BEP Revenue</div><div className="kpi-value text-2xl">{fmtIDR(res.bep_revenue)}</div></div>
            </div>
          )}
        </div>
        <div className="p-6 rounded-lg border border-border bg-card">
          {chartData.length===0 && <div className="text-sm text-muted-foreground text-center py-16">Hitung untuk melihat grafik.</div>}
          {chartData.length>0 && (
            <ResponsiveContainer width="100%" height={360}>
              <BarChart data={chartData}>
                <XAxis dataKey="units" tick={{fontSize:11}}/>
                <YAxis tick={{fontSize:11}} tickFormatter={(v)=>`${(v/1000).toFixed(0)}k`}/>
                <Tooltip formatter={v=>fmtIDR(v)} contentStyle={{fontSize:12,border:"1px solid #e5e7eb",borderRadius:8}}/>
                <Legend wrapperStyle={{fontSize:11}}/>
                <Bar dataKey="revenue" fill="#0f172a" name="Revenue"/>
                <Bar dataKey="total_cost" fill="#dc2626" name="Total Cost"/>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  );
}

export function Reports() {
  const [pl, setPl] = useState(null);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const load = useCallback(async () => {
    const { data } = await api.get(`/reports/profit_loss?start=${start}&end=${end}`);
    setPl(data);
  }, [start, end]);
  useEffect(() => { load(); }, [load]);
  const exportCSV = () => {
    const q = new URLSearchParams(); if (start) q.set("start", start); if (end) q.set("end", end);
    downloadCSV(`/reports/export/profit_loss?${q.toString()}`, "profit_loss.csv");
  };
  return (
    <div>
      <PageHeader title="Reports" subtitle="Profit & Loss" action={
        <div className="flex gap-2 print:hidden">
          <Button variant="outline" onClick={() => downloadCSV("/reports/export/sales", "sales_export.csv")} data-testid="btn-export-sales-report"><Download size={14} className="inline mr-1"/> Sales CSV</Button>
          <Button variant="outline" onClick={() => downloadCSV("/reports/export/inventory", "inventory_export.csv")} data-testid="btn-export-inventory"><Download size={14} className="inline mr-1"/> Inventory CSV</Button>
          <Button variant="outline" onClick={exportCSV} data-testid="btn-export-pl"><Download size={14} className="inline mr-1"/> P&L CSV</Button>
          <Button variant="outline" onClick={printPage} data-testid="btn-print"><Printer size={14} className="inline mr-1"/> Print / PDF</Button>
        </div>
      }/>
      <div className="p-6 rounded-lg border border-border bg-card">
        <div className="flex gap-3 items-end mb-4">
          <Field label="Start"><Input type="date" value={start} onChange={e=>setStart(e.target.value)}/></Field>
          <Field label="End"><Input type="date" value={end} onChange={e=>setEnd(e.target.value)}/></Field>
          <Button onClick={load} data-testid="btn-load-pl">Generate</Button>
        </div>
        {!pl && <Button onClick={load} className="mt-2">Load P&L</Button>}
        {pl && (
          <div className="grid grid-cols-2 gap-4 mt-4" data-testid="pl-report">
            <Row2 label="Revenue" v={pl.revenue} tone="pos"/>
            <Row2 label="COGS/HPP" v={-pl.cogs} tone="neg"/>
            <Row2 label="Gross Profit" v={pl.gross_profit} tone="pos" bold/>
            <Row2 label="Marketplace Fees" v={-pl.marketplace_fees} tone="neg"/>
            <Row2 label="Advertising" v={-pl.advertising} tone="neg"/>
            <Row2 label="Operating Expenses" v={-pl.operating_expenses} tone="neg"/>
            <Row2 label="Net Profit" v={pl.net_profit} tone={pl.net_profit>=0?"pos":"neg"} bold big/>
          </div>
        )}
      </div>
    </div>
  );
}
function Row2({ label, v, tone, bold, big }) {
  const c = tone==="pos"?"text-emerald-600":"text-rose-600";
  return <div className={`p-4 rounded-md border border-border ${bold?"bg-stone-100 dark:bg-stone-900":""}`}><div className="text-[10px] uppercase font-bold tracking-widest text-muted-foreground">{label}</div><div className={`font-display font-bold ${big?"text-3xl":"text-xl"} ${c}`}>{fmtIDR(v)}</div></div>;
}
