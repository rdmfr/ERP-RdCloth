import { useState, useEffect } from "react";
import { PageHeader, DataTable, Modal, Field, Input, Select, Button, StatusPill, useCRUD, Plus, Trash2 } from "./_shared";
import { api, fmtIDR, fmtNum, fmtDate, formatErr } from "@/lib/api";
import { toast } from "sonner";

export function Purchasing() {
  const [rows, setRows] = useState([]);
  const [creating, setCreating] = useState(false);
  const [paying, setPaying] = useState(null);
  const { rows: suppliers } = useCRUD("suppliers");
  const { rows: materials } = useCRUD("materials");
  const { rows: accounts } = useCRUD("accounts");

  const reload = () => api.get("/purchase_orders").then(r=>setRows(r.data));
  useEffect(() => { reload(); }, []);

  const receive = async (id) => {
    if (!confirm("Terima PO ini? Stok akan bertambah.")) return;
    try { await api.post(`/purchase_orders/${id}/receive`); toast.success("PO diterima"); reload(); }
    catch (e) { toast.error(formatErr(e.response?.data?.detail)); }
  };
  const pay = async () => {
    try { await api.post(`/purchase_orders/${paying.id}/pay`, { account_id:paying.account_id }); toast.success("Hutang supplier dilunasi"); setPaying(null); reload(); }
    catch (e) { toast.error(formatErr(e.response?.data?.detail)); }
  };

  return (
    <div>
      <PageHeader title="Purchasing" subtitle="Purchase orders ke supplier" action={
        <Button onClick={()=>setCreating(true)} data-testid="btn-new-po"><Plus size={14} className="inline mr-1"/> PO Baru</Button>
      }/>
      <DataTable testid="po-table" rows={rows}
        columns={[
          { header:"PO #", cell:r=><span className="font-mono text-xs font-semibold">{r.po_number}</span> },
          { header:"Date", cell:r=>fmtDate(r.date) },
          { header:"Supplier", cell:r=>suppliers.find(s=>s.id===r.supplier_id)?.name||"-" },
          { header:"Items", cell:r=>fmtNum((r.items||[]).length) },
          { header:"Total", cell:r=><span className="font-bold">{fmtIDR(r.total)}</span> },
          { header:"Payment", cell:r=><StatusPill status={r.payment_status}/> },
          { header:"Received", cell:r=><StatusPill status={r.received_status}/> },
          { header:"", cell:r=><div className="flex gap-2">{r.received_status!=="received" && <Button variant="outline" onClick={()=>receive(r.id)} data-testid={`receive-po-${r.id}`}>Receive</Button>}{r.received_status==="received" && r.payment_status!=="paid" && <Button variant="outline" onClick={()=>setPaying({id:r.id,account_id:accounts.find(a=>a.is_default)?.id||accounts[0]?.id||""})}>Bayar Hutang</Button>}</div> },
        ]}/>
      {creating && <POForm suppliers={suppliers} materials={materials} accounts={accounts} onClose={()=>setCreating(false)} onDone={()=>{ setCreating(false); reload(); }} />}
      {paying && <Modal open onClose={()=>setPaying(null)} title="Bayar Hutang Supplier"><Field label="Bayar dari akun"><Select value={paying.account_id} onChange={e=>setPaying({...paying,account_id:e.target.value})}>{accounts.map(a=><option key={a.id} value={a.id}>{a.name} ({fmtIDR(a.balance||0)})</option>)}</Select></Field><div className="flex justify-end gap-2 mt-6"><Button variant="outline" onClick={()=>setPaying(null)}>Batal</Button><Button onClick={pay}>Bayar</Button></div></Modal>}
    </div>
  );
}

function POForm({ suppliers, materials, accounts, onClose, onDone }) {
  const defaultAccount = accounts.find(a=>a.is_default)?.id || accounts[0]?.id || "";
  const [form, setForm] = useState({ supplier_id:"", account_id:defaultAccount, date: new Date().toISOString().slice(0,10), items:[], discount:0, shipping:0, tax:0, payment_status:"unpaid" });
  const [row, setRow] = useState({ material_id:"", quantity:1, unit_cost:0 });
  const add = () => {
    const m = materials.find(x=>x.id===row.material_id); if (!m) return;
    setForm(f=>({...f, items:[...f.items, { material_id:m.id, material_name:m.name, quantity:Number(row.quantity), unit_cost:Number(row.unit_cost)||Number(m.cost) }]}));
    setRow({ material_id:"", quantity:1, unit_cost:0 });
  };
  const subtotal = form.items.reduce((s,i)=>s+i.quantity*i.unit_cost,0);
  const total = subtotal - Number(form.discount) + Number(form.shipping) + Number(form.tax);

  const submit = async () => {
    try { await api.post("/purchase_orders", { ...form, total }); toast.success("PO dibuat"); onDone(); }
    catch (e) { toast.error(formatErr(e.response?.data?.detail)); }
  };

  return (
    <Modal open onClose={onClose} title="Purchase Order Baru">
      <div className="grid grid-cols-2 gap-4 mb-4">
        <Field label="Supplier">
          <Select value={form.supplier_id} onChange={e=>setForm({...form,supplier_id:e.target.value})} data-testid="po-supplier">
            <option value="">-- Pilih --</option>
            {suppliers.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}
          </Select>
        </Field>
        <Field label="Tanggal"><Input type="date" value={form.date} onChange={e=>setForm({...form,date:e.target.value})}/></Field>
        <Field label="Bayar dari akun">
          <Select value={form.account_id} onChange={e=>setForm({...form,account_id:e.target.value})} data-testid="po-account">
            <option value="">-- Pilih akun --</option>
            {accounts.map(a=><option key={a.id} value={a.id}>{a.name} ({fmtIDR(a.balance||0)})</option>)}
          </Select>
        </Field>
      </div>
      <div className="text-[10px] uppercase font-bold tracking-widest text-muted-foreground mb-2">Items</div>
      <div className="grid grid-cols-[1fr_100px_140px_auto] gap-2 items-end mb-2">
        <Field label="Material"><Select value={row.material_id} onChange={e=>{const m=materials.find(x=>x.id===e.target.value); setRow({...row,material_id:e.target.value,unit_cost:m?.cost||0});}}>
          <option value="">-- Pilih --</option>
          {materials.map(m=><option key={m.id} value={m.id}>{m.name}</option>)}
        </Select></Field>
        <Field label="Qty"><Input type="number" value={row.quantity} onChange={e=>setRow({...row,quantity:e.target.value})}/></Field>
        <Field label="Unit Cost"><Input type="number" value={row.unit_cost} onChange={e=>setRow({...row,unit_cost:e.target.value})}/></Field>
        <Button variant="outline" onClick={add} data-testid="po-add-item"><Plus size={14}/></Button>
      </div>
      <div className="border border-border rounded-md">
        {form.items.length===0 && <div className="p-3 text-center text-sm text-muted-foreground">Belum ada item</div>}
        {form.items.map((it,i)=>(
          <div key={i} className="flex items-center justify-between p-2 border-b border-border last:border-0 text-sm">
            <span>{it.material_name} × {it.quantity} @ {fmtIDR(it.unit_cost)}</span>
            <div className="flex items-center gap-3">
              <span className="font-bold">{fmtIDR(it.quantity*it.unit_cost)}</span>
              <button onClick={()=>setForm(f=>({...f, items:f.items.filter((_,x)=>x!==i)}))}><Trash2 size={14} className="text-rose-500"/></button>
            </div>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-3 gap-3 mt-4">
        <Field label="Discount"><Input type="number" value={form.discount} onChange={e=>setForm({...form,discount:e.target.value})}/></Field>
        <Field label="Shipping"><Input type="number" value={form.shipping} onChange={e=>setForm({...form,shipping:e.target.value})}/></Field>
        <Field label="Tax"><Input type="number" value={form.tax} onChange={e=>setForm({...form,tax:e.target.value})}/></Field>
      </div>
      <div className="mt-4 flex items-center justify-between border-t border-border pt-4">
        <div>
          <div className="text-xs text-muted-foreground">Subtotal: {fmtIDR(subtotal)}</div>
          <div className="text-xl font-bold font-display">Total: {fmtIDR(total)}</div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onClose}>Batal</Button>
          <Button onClick={submit} data-testid="btn-save-po">Simpan PO</Button>
        </div>
      </div>
    </Modal>
  );
}

export function Production() {
  const [rows, setRows] = useState([]);
  const [creating, setCreating] = useState(false);
  const [completing, setCompleting] = useState(null);
  const { rows: products } = useCRUD("products");
  const { rows: materials } = useCRUD("materials");
  const { rows: boms } = useCRUD("boms");

  const reload = () => api.get("/production_orders").then(r=>setRows(r.data));
  useEffect(() => { reload(); }, []);

  const complete = async () => {
    try { await api.post(`/production_orders/${completing.id}/complete`, completing); toast.success("Produksi selesai"); setCompleting(null); reload(); }
    catch (e) { toast.error(formatErr(e.response?.data?.detail)); }
  };

  return (
    <div>
      <PageHeader title="Production" subtitle="Production orders & QC" action={
        <Button onClick={()=>setCreating(true)} data-testid="btn-new-prod"><Plus size={14} className="inline mr-1"/> Order Produksi</Button>
      }/>
      <DataTable testid="prod-table" rows={rows}
        columns={[
          { header:"Prod #", cell:r=><span className="font-mono text-xs font-semibold">{r.prod_number}</span> },
          { header:"Product", cell:r=>r.product_name || products.find(p=>p.id===r.product_id)?.name || "-" },
          { header:"Variant", cell:r=><span className="font-mono text-xs">{r.variant_sku||"-"}</span> },
          { header:"Qty", cell:r=>fmtNum(r.quantity) },
          { header:"Passed", cell:r=>fmtNum(r.quantity_passed||0) },
          { header:"Rejected", cell:r=>fmtNum(r.quantity_rejected||0) },
          { header:"Status", cell:r=><StatusPill status={r.status}/> },
          { header:"", cell:r=>r.status!=="completed" && <Button variant="outline" onClick={()=>setCompleting({id:r.id,quantity_passed:r.quantity,quantity_rejected:0})} data-testid={`complete-prod-${r.id}`}>Complete</Button> },
        ]}/>

      {creating && <ProdForm products={products} materials={materials} boms={boms} onClose={()=>setCreating(false)} onDone={()=>{ setCreating(false); reload(); }} />}

      {completing && <Modal open onClose={()=>setCompleting(null)} title="Selesaikan Produksi">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Quantity Passed"><Input type="number" value={completing.quantity_passed} onChange={e=>setCompleting({...completing,quantity_passed:e.target.value})}/></Field>
          <Field label="Quantity Rejected"><Input type="number" value={completing.quantity_rejected} onChange={e=>setCompleting({...completing,quantity_rejected:e.target.value})}/></Field>
        </div>
        <div className="text-xs text-muted-foreground mt-3">Bahan baku akan dikonsumsi dari inventory, dan produk jadi akan ditambahkan.</div>
        <div className="flex justify-end gap-2 mt-6"><Button variant="outline" onClick={()=>setCompleting(null)}>Batal</Button><Button onClick={complete} data-testid="btn-confirm-complete">Konfirmasi</Button></div>
      </Modal>}
    </div>
  );
}

function ProdForm({ products, materials, boms, onClose, onDone }) {
  const [form, setForm] = useState({ product_id:"", variant_sku:"", quantity:1, bom_items:[], date:new Date().toISOString().slice(0,10) });
  const selectedProd = products.find(p=>p.id===form.product_id);
  const applyBom = (bomId) => {
    const bom = boms.find(b=>b.id===bomId); if (!bom) return;
    setForm(f=>({...f, bom_items: bom.items}));
  };

  const submit = async () => {
    if (!form.product_id||!form.variant_sku||form.bom_items.length===0) { toast.error("Lengkapi form"); return; }
    try {
      await api.post("/production_orders", { ...form, product_name: selectedProd?.name, status:"planned" });
      toast.success("Order produksi dibuat");
      onDone();
    } catch (e) { toast.error(formatErr(e.response?.data?.detail)); }
  };

  return (
    <Modal open onClose={onClose} title="Production Order Baru">
      <div className="grid grid-cols-2 gap-4 mb-4">
        <Field label="Product">
          <Select value={form.product_id} onChange={e=>setForm({...form,product_id:e.target.value,variant_sku:""})} data-testid="prod-product">
            <option value="">-- Pilih --</option>
            {products.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
          </Select>
        </Field>
        <Field label="Variant">
          <Select value={form.variant_sku} onChange={e=>setForm({...form,variant_sku:e.target.value})} data-testid="prod-variant">
            <option value="">-- Pilih --</option>
            {(selectedProd?.variants||[]).map(v=><option key={v.sku} value={v.sku}>{v.sku} · {v.color}/{v.size}</option>)}
          </Select>
        </Field>
        <Field label="Quantity"><Input type="number" value={form.quantity} onChange={e=>setForm({...form,quantity:e.target.value})}/></Field>
        <Field label="BOM Template">
          <Select onChange={e=>applyBom(e.target.value)}>
            <option value="">-- Manual --</option>
            {boms.map(b=><option key={b.id} value={b.id}>{b.product_name}</option>)}
          </Select>
        </Field>
      </div>

      <div className="text-[10px] uppercase font-bold tracking-widest text-muted-foreground mb-2">BOM (Bahan Baku per Unit)</div>
      <div className="space-y-2">
        {form.bom_items.map((it,i)=>(
          <div key={i} className="grid grid-cols-[1fr_100px_auto] gap-2 items-center">
            <Select value={it.material_id} onChange={e=>{const m=materials.find(x=>x.id===e.target.value); setForm(f=>({...f, bom_items:f.bom_items.map((x,idx)=>idx===i?{...x,material_id:e.target.value,material_name:m?.name}:x)}));}}>
              <option value="">-- Pilih Material --</option>
              {materials.map(m=><option key={m.id} value={m.id}>{m.name}</option>)}
            </Select>
            <Input type="number" step="0.1" value={it.quantity} onChange={e=>setForm(f=>({...f, bom_items:f.bom_items.map((x,idx)=>idx===i?{...x,quantity:e.target.value}:x)}))}/>
            <button onClick={()=>setForm(f=>({...f, bom_items:f.bom_items.filter((_,x)=>x!==i)}))}><Trash2 size={14} className="text-rose-500"/></button>
          </div>
        ))}
      </div>
      <Button variant="outline" onClick={()=>setForm(f=>({...f, bom_items:[...f.bom_items,{material_id:"",quantity:1}]}))} className="mt-2" data-testid="prod-add-material"><Plus size={14} className="inline"/> Bahan</Button>

      <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-border">
        <Button variant="outline" onClick={onClose}>Batal</Button>
        <Button onClick={submit} data-testid="btn-save-prod">Simpan</Button>
      </div>
    </Modal>
  );
}
