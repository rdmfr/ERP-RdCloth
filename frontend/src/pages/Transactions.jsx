import { useCallback, useState, useEffect } from "react";
import { PageHeader, DataTable, Modal, Field, Input, Select, Button, StatusPill, useCRUD, Plus, Trash2 } from "./_shared";
import { api, fmtIDR, fmtNum, fmtDate, formatErr } from "@/lib/api";
import { downloadCSV } from "@/lib/export";
import { toast } from "sonner";

export function Sales() {
  const [rows, setRows] = useState([]);
  const [creating, setCreating] = useState(false);
  const { rows: products } = useCRUD("products");
  const { rows: customers } = useCRUD("customers");
  const { rows: marketplaces } = useCRUD("marketplaces");

  const reload = useCallback(() => api.get("/sales_orders").then(r=>setRows(r.data)), []);
  useEffect(() => { reload(); }, [reload]);

  const cancel = async (id) => {
    if (!confirm("Batalkan order ini? Stok akan dikembalikan dan cash akan di-refund.")) return;
    try {
      await api.post(`/sales_orders/${id}/cancel`);
      toast.success("Order dibatalkan. Stok & cash dikembalikan.");
      reload();
    } catch (e) { toast.error(formatErr(e.response?.data?.detail)); }
  };

  return (
    <div>
      <PageHeader title="Sales Orders" subtitle="Penjualan & channel" action={
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => downloadCSV("/reports/export/sales", "sales_export.csv")} data-testid="btn-export-sales">Export CSV</Button>
          <Button onClick={()=>setCreating(true)} data-testid="btn-new-sale"><Plus size={14} className="inline mr-1"/> Order Baru</Button>
        </div>
      }/>
      <DataTable testid="sales-table" rows={rows}
        columns={[
          { header:"Order #", cell:r=><span className="font-mono text-xs font-semibold">{r.order_number}</span> },
          { header:"Date", cell:r=>fmtDate(r.date) },
          { header:"Customer", cell:r=>r.customer_name||customers.find(c=>c.id===r.customer_id)?.name||"-" },
          { header:"Channel", cell:r=>r.sales_channel },
          { header:"Items", cell:r=>fmtNum((r.items||[]).length) },
          { header:"Subtotal", cell:r=>fmtIDR(r.subtotal) },
          { header:"MP Fee", cell:r=><span className="text-rose-600">-{fmtIDR(r.marketplace_fee)}</span> },
          { header:"Total", cell:r=><span className="font-bold">{fmtIDR(r.total)}</span> },
          { header:"Profit", cell:r=><span className={r.net_profit>=0?"text-emerald-600 font-semibold":"text-rose-600 font-semibold"}>{fmtIDR(r.net_profit)}</span> },
          { header:"Payment", cell:r=><StatusPill status={r.payment_status}/> },
          { header:"Fulfillment", cell:r=><StatusPill status={r.fulfillment_status}/> },
          { header:"", cell:r=>r.fulfillment_status!=="cancelled" && <button onClick={()=>cancel(r.id)} data-testid={`cancel-sale-${r.id}`} className="text-xs text-rose-600 hover:underline font-semibold">Cancel</button>},
        ]}/>
      {creating && <SalesForm products={products} customers={customers} marketplaces={marketplaces} onClose={()=>setCreating(false)} onDone={()=>{ setCreating(false); reload(); }} />}
    </div>
  );
}

function SalesForm({ products, customers, marketplaces, onClose, onDone }) {
  const [form, setForm] = useState({
    customer_id:"", customer_name:"", sales_channel:"Direct/Offline", items:[],
    discount:0, voucher:0, shipping:0, other_fee:0, advertising_cost:0,
    payment_status:"paid", fulfillment_status:"processing", date:new Date().toISOString(),
  });
  const [row, setRow] = useState({ product_id:"", variant_sku:"", quantity:1, selling_price:0 });
  const selP = products.find(p=>p.id===row.product_id);
  const selV = selP?.variants.find(v=>v.sku===row.variant_sku);

  const add = () => {
    if (!row.product_id || !row.variant_sku) { toast.error("Pilih product & variant"); return; }
    const p = products.find(x=>x.id===row.product_id);
    setForm(f=>({...f, items:[...f.items, {
      product_id: row.product_id, product_name: p.name, variant_sku: row.variant_sku,
      quantity: Number(row.quantity), selling_price: Number(row.selling_price)||Number(selV?.selling_price||0),
    }]}));
    setRow({ product_id:"", variant_sku:"", quantity:1, selling_price:0 });
  };

  const mp = marketplaces.find(m=>m.name===form.sales_channel);
  const mpFeePct = mp ? Number(mp.admin_fee_pct||0)+Number(mp.service_fee_pct||0)+Number(mp.payment_fee_pct||0) : 0;
  const subtotal = form.items.reduce((s,i)=>s+i.quantity*i.selling_price,0);
  const mpFee = subtotal * mpFeePct / 100;
  const total = subtotal - Number(form.discount) - Number(form.voucher) + Number(form.shipping);

  const submit = async () => {
    if (form.items.length===0) { toast.error("Tambahkan minimal 1 item"); return; }
    try {
      const cust = customers.find(c=>c.id===form.customer_id);
      await api.post("/sales_orders", {
        ...form, marketplace_fee: mpFee,
        customer_name: cust?.name || form.customer_name || "Guest",
      });
      toast.success("Order dibuat & stok berkurang");
      onDone();
    } catch (e) { toast.error(formatErr(e.response?.data?.detail)); }
  };

  return (
    <Modal open onClose={onClose} title="Sales Order Baru">
      <div className="grid grid-cols-2 gap-4 mb-4">
        <Field label="Customer">
          <Select value={form.customer_id} onChange={e=>setForm({...form,customer_id:e.target.value})} data-testid="sale-customer">
            <option value="">-- Guest --</option>
            {customers.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
          </Select>
        </Field>
        <Field label="Channel">
          <Select value={form.sales_channel} onChange={e=>setForm({...form,sales_channel:e.target.value})} data-testid="sale-channel">
            {marketplaces.map(m=><option key={m.id} value={m.name}>{m.name}</option>)}
          </Select>
        </Field>
      </div>

      <div className="text-[10px] uppercase font-bold tracking-widest text-muted-foreground mb-2">Items</div>
      <div className="grid grid-cols-[1fr_1fr_80px_120px_auto] gap-2 items-end mb-2">
        <Field label="Product">
          <Select value={row.product_id} onChange={e=>setRow({...row,product_id:e.target.value,variant_sku:""})}>
            <option value="">-- Pilih --</option>
            {products.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
          </Select>
        </Field>
        <Field label="Variant">
          <Select value={row.variant_sku} onChange={e=>{const v=selP?.variants.find(x=>x.sku===e.target.value); setRow({...row,variant_sku:e.target.value,selling_price:v?.selling_price||0});}}>
            <option value="">-- Pilih --</option>
            {selP?.variants.map(v=><option key={v.sku} value={v.sku}>{v.sku} (stock: {v.stock})</option>)}
          </Select>
        </Field>
        <Field label="Qty"><Input type="number" value={row.quantity} onChange={e=>setRow({...row,quantity:e.target.value})}/></Field>
        <Field label="Price"><Input type="number" value={row.selling_price} onChange={e=>setRow({...row,selling_price:e.target.value})}/></Field>
        <Button variant="outline" onClick={add} data-testid="sale-add-item"><Plus size={14}/></Button>
      </div>
      <div className="border border-border rounded-md">
        {form.items.length===0 && <div className="p-3 text-center text-sm text-muted-foreground">Belum ada item</div>}
        {form.items.map((it,i)=>(
          <div key={i} className="flex items-center justify-between p-2 border-b border-border last:border-0 text-sm">
            <span>{it.product_name} ({it.variant_sku}) × {it.quantity} @ {fmtIDR(it.selling_price)}</span>
            <div className="flex items-center gap-3">
              <span className="font-bold">{fmtIDR(it.quantity*it.selling_price)}</span>
              <button onClick={()=>setForm(f=>({...f, items:f.items.filter((_,x)=>x!==i)}))}><Trash2 size={14} className="text-rose-500"/></button>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-3 mt-4">
        <Field label="Discount"><Input type="number" value={form.discount} onChange={e=>setForm({...form,discount:e.target.value})}/></Field>
        <Field label="Voucher"><Input type="number" value={form.voucher} onChange={e=>setForm({...form,voucher:e.target.value})}/></Field>
        <Field label="Shipping"><Input type="number" value={form.shipping} onChange={e=>setForm({...form,shipping:e.target.value})}/></Field>
        <Field label="Advertising"><Input type="number" value={form.advertising_cost} onChange={e=>setForm({...form,advertising_cost:e.target.value})}/></Field>
        <Field label="Payment">
          <Select value={form.payment_status} onChange={e=>setForm({...form,payment_status:e.target.value})}>
            <option value="paid">Paid</option><option value="unpaid">Unpaid</option>
          </Select>
        </Field>
        <Field label="Fulfillment">
          <Select value={form.fulfillment_status} onChange={e=>setForm({...form,fulfillment_status:e.target.value})}>
            <option value="processing">Processing</option><option value="shipped">Shipped</option><option value="completed">Completed</option>
          </Select>
        </Field>
      </div>

      <div className="mt-4 pt-4 border-t border-border space-y-1 text-sm">
        <div className="flex justify-between"><span className="text-muted-foreground">Subtotal</span><span>{fmtIDR(subtotal)}</span></div>
        <div className="flex justify-between"><span className="text-muted-foreground">Marketplace Fee ({mpFeePct}%)</span><span className="text-rose-600">-{fmtIDR(mpFee)}</span></div>
        <div className="flex justify-between font-bold text-lg font-display"><span>Total</span><span>{fmtIDR(total)}</span></div>
      </div>
      <div className="flex justify-end gap-2 mt-4">
        <Button variant="outline" onClick={onClose}>Batal</Button>
        <Button onClick={submit} data-testid="btn-save-sale">Simpan & Kurangi Stok</Button>
      </div>
    </Modal>
  );
}

export function Finance() {
  const [txns, setTxns] = useState([]);
  const [expenses, setExpenses] = useState([]);
  const [tab, setTab] = useState("txns");
  const { rows: accounts, reload: reloadAcc } = useCRUD("accounts");
  const [txnModal, setTxnModal] = useState(null);
  const [expModal, setExpModal] = useState(null);
  const { rows: expCats } = useCRUD("expense_categories");

  const reload = useCallback(async () => {
    setTxns((await api.get("/financial_transactions")).data);
    setExpenses((await api.get("/expenses")).data);
    reloadAcc();
  }, [reloadAcc]);
  useEffect(() => { reload(); }, [reload]);

  const saveTxn = async () => {
    try { await api.post("/financial_transactions", txnModal); toast.success("Transaksi tersimpan"); setTxnModal(null); reload(); }
    catch (e) { toast.error(formatErr(e.response?.data?.detail)); }
  };
  const saveExp = async () => {
    try { await api.post("/expenses", expModal); toast.success("Expense tersimpan"); setExpModal(null); reload(); }
    catch (e) { toast.error(formatErr(e.response?.data?.detail)); }
  };

  return (
    <div>
      <PageHeader title="Finance" subtitle="Cash, expenses, capital" action={
        <div className="flex gap-2">
          <Button variant="outline" onClick={()=>setExpModal({description:"",amount:0,category:"Other",account_id:accounts[0]?.id})} data-testid="btn-new-expense"><Plus size={14} className="inline mr-1"/> Expense</Button>
          <Button onClick={()=>setTxnModal({type:"owner_investment",amount:0,description:"",account_id:accounts[0]?.id})} data-testid="btn-new-txn"><Plus size={14} className="inline mr-1"/> Transaksi</Button>
        </div>
      }/>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {accounts.map(a=>(
          <div key={a.id} className="p-5 rounded-lg border border-border bg-card">
            <div className="text-[10px] uppercase font-bold tracking-widest text-muted-foreground">{a.kind}</div>
            <div className="font-semibold text-sm">{a.name}</div>
            <div className="kpi-value text-3xl mt-2">{fmtIDR(a.balance)}</div>
          </div>
        ))}
      </div>

      <div className="flex gap-2 mb-4">
        {[["txns","Transactions"],["expenses","Expenses"]].map(([k,l])=>(
          <button key={k} onClick={()=>setTab(k)} data-testid={`fin-tab-${k}`}
            className={`px-4 py-2 rounded-md text-xs font-semibold uppercase tracking-widest ${tab===k?"bg-neutral-900 text-white dark:bg-stone-100 dark:text-stone-900":"bg-stone-100 dark:bg-stone-900"}`}>{l}</button>
        ))}
      </div>

      {tab==="txns" && (
        <DataTable testid="txns-table" rows={txns}
          columns={[
            {header:"Date",cell:r=>fmtDate(r.date)},
            {header:"Type",cell:r=><StatusPill status={r.type.includes("income")||r.type==="owner_investment"?"paid":"processing"}/>},
            {header:"Description",cell:r=>r.description},
            {header:"Account",cell:r=>accounts.find(a=>a.id===r.account_id)?.name||"-"},
            {header:"Amount",cell:r=><span className={r.type==="income"||r.type==="owner_investment"?"text-emerald-600 font-bold":"text-rose-600 font-bold"}>{r.type==="income"||r.type==="owner_investment"?"+":"-"}{fmtIDR(r.amount)}</span>},
          ]}/>
      )}
      {tab==="expenses" && (
        <DataTable testid="expenses-table" rows={expenses}
          columns={[
            {header:"Date",cell:r=>fmtDate(r.date)},
            {header:"Category",cell:r=>r.category},
            {header:"Description",cell:r=>r.description},
            {header:"Amount",cell:r=><span className="font-bold text-rose-600">-{fmtIDR(r.amount)}</span>},
          ]}/>
      )}

      {txnModal && <Modal open onClose={()=>setTxnModal(null)} title="Transaksi Keuangan">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Tipe"><Select value={txnModal.type} onChange={e=>setTxnModal({...txnModal,type:e.target.value})}>
            <option value="owner_investment">Owner Investment (Modal)</option>
            <option value="owner_withdrawal">Owner Withdrawal (Prive)</option>
            <option value="income">Income</option>
            <option value="expense">Expense</option>
          </Select></Field>
          <Field label="Account"><Select value={txnModal.account_id} onChange={e=>setTxnModal({...txnModal,account_id:e.target.value})}>
            {accounts.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}
          </Select></Field>
          <Field label="Amount"><Input type="number" value={txnModal.amount} onChange={e=>setTxnModal({...txnModal,amount:e.target.value})}/></Field>
          <Field label="Description"><Input value={txnModal.description} onChange={e=>setTxnModal({...txnModal,description:e.target.value})}/></Field>
        </div>
        <div className="flex justify-end gap-2 mt-6"><Button variant="outline" onClick={()=>setTxnModal(null)}>Batal</Button><Button onClick={saveTxn} data-testid="btn-confirm-txn">Simpan</Button></div>
      </Modal>}

      {expModal && <Modal open onClose={()=>setExpModal(null)} title="Expense Baru">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Category"><Select value={expModal.category} onChange={e=>setExpModal({...expModal,category:e.target.value})}>
            {expCats.map(c=><option key={c.id} value={c.name}>{c.name}</option>)}
          </Select></Field>
          <Field label="Amount"><Input type="number" value={expModal.amount} onChange={e=>setExpModal({...expModal,amount:e.target.value})}/></Field>
          <Field label="Account"><Select value={expModal.account_id} onChange={e=>setExpModal({...expModal,account_id:e.target.value})}>
            {accounts.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}
          </Select></Field>
          <Field label="Description"><Input value={expModal.description} onChange={e=>setExpModal({...expModal,description:e.target.value})}/></Field>
        </div>
        <div className="flex justify-end gap-2 mt-6"><Button variant="outline" onClick={()=>setExpModal(null)}>Batal</Button><Button onClick={saveExp} data-testid="btn-confirm-expense">Simpan</Button></div>
      </Modal>}
    </div>
  );
}
