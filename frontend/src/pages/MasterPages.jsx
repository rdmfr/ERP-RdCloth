import { useState, useEffect } from "react";
import { PageHeader, DataTable, Modal, Field, Input, Select, Button, StatusPill, useCRUD, Plus, Edit, Trash2 } from "./_shared";
import { api, fmtIDR, fmtNum, formatErr } from "@/lib/api";
import { toast } from "sonner";

export function Materials() {
  const { rows, save, remove, reload } = useCRUD("materials");
  const { rows: suppliers } = useCRUD("suppliers");
  const [editing, setEditing] = useState(null);
  const openNew = () => setEditing({ name:"", unit:"pcs", stock:0, cost:0, minimum_stock:0 });

  return (
    <div>
      <PageHeader title="Materials" subtitle="Raw materials & bahan baku" action={
        <Button onClick={openNew} data-testid="btn-new-material"><Plus size={14} className="inline mr-1"/> Bahan Baku</Button>
      }/>
      <DataTable
        testid="materials-table"
        columns={[
          { header: "Name", cell: r => <span className="font-semibold">{r.name}</span> },
          { header: "Unit", cell: r => r.unit },
          { header: "Stock", cell: r => fmtNum(r.stock) },
          { header: "Cost/Unit", cell: r => fmtIDR(r.cost) },
          { header: "Total Value", cell: r => fmtIDR(Number(r.stock)*Number(r.cost)) },
          { header: "Min Stock", cell: r => fmtNum(r.minimum_stock) },
          { header: "Supplier", cell: r => suppliers.find(s=>s.id===r.supplier_id)?.name || "-" },
          { header: "Status", cell: r => <StatusPill status={Number(r.stock)===0?"out_of_stock":(Number(r.stock)<=Number(r.minimum_stock)?"low_stock":"ok")}/> },
          { header: "", cell: r => (
            <div className="flex gap-2">
              <button onClick={()=>setEditing(r)}><Edit size={14}/></button>
              <button onClick={()=>remove(r.id)}><Trash2 size={14} className="text-rose-500"/></button>
            </div>
          )},
        ]}
        rows={rows}
      />
      {editing && <Modal open onClose={()=>setEditing(null)} title={editing.id?"Edit Bahan":"Bahan Baru"}>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Nama"><Input value={editing.name} onChange={e=>setEditing({...editing,name:e.target.value})}/></Field>
          <Field label="Unit"><Input value={editing.unit} onChange={e=>setEditing({...editing,unit:e.target.value})}/></Field>
          <Field label="Stock"><Input type="number" value={editing.stock} onChange={e=>setEditing({...editing,stock:Number(e.target.value)})}/></Field>
          <Field label="Cost/Unit"><Input type="number" value={editing.cost} onChange={e=>setEditing({...editing,cost:Number(e.target.value)})}/></Field>
          <Field label="Minimum Stock"><Input type="number" value={editing.minimum_stock} onChange={e=>setEditing({...editing,minimum_stock:Number(e.target.value)})}/></Field>
          <Field label="Supplier">
            <Select value={editing.supplier_id||""} onChange={e=>setEditing({...editing,supplier_id:e.target.value})}>
              <option value="">-- Pilih --</option>
              {suppliers.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}
            </Select>
          </Field>
        </div>
        <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-border">
          <Button variant="outline" onClick={()=>setEditing(null)}>Batal</Button>
          <Button onClick={async()=>{ if (await save(editing, editing.id)) setEditing(null); }}>Simpan</Button>
        </div>
      </Modal>}
    </div>
  );
}

export function Inventory() {
  const [movements, setMovements] = useState([]);
  const [tab, setTab] = useState("products");
  const { rows: products } = useCRUD("products");
  const { rows: materials, reload: reloadMats } = useCRUD("materials");
  const [adjust, setAdjust] = useState(null);

  useEffect(() => { api.get("/inventory/movements").then(r=>setMovements(r.data)); }, []);

  const doAdjust = async () => {
    try {
      if (adjust.kind === "material") {
        await api.post("/inventory/materials/adjust", { material_id: adjust.id, quantity: Number(adjust.qty), type: adjust.type, notes: adjust.notes });
      } else {
        await api.post("/inventory/products/adjust", { product_id: adjust.pid, variant_sku: adjust.sku, quantity: Number(adjust.qty), type: adjust.type, notes: adjust.notes });
      }
      toast.success("Stok diperbarui");
      setAdjust(null);
      reloadMats();
      api.get("/inventory/movements").then(r=>setMovements(r.data));
    } catch (e) { toast.error(formatErr(e.response?.data?.detail)); }
  };

  return (
    <div>
      <PageHeader title="Inventory" subtitle="Stock movements & alerts"/>
      <div className="flex gap-2 mb-4">
        {[["products","Products"],["materials","Materials"],["movements","Movements"]].map(([k,l])=>(
          <button key={k} onClick={()=>setTab(k)} data-testid={`inv-tab-${k}`}
            className={`px-4 py-2 rounded-md text-xs font-semibold uppercase tracking-widest ${tab===k?"bg-neutral-900 text-white dark:bg-stone-100 dark:text-stone-900":"bg-stone-100 dark:bg-stone-900"}`}>{l}</button>
        ))}
      </div>
      {tab==="products" && (
        <DataTable testid="inv-products-table" rows={products.flatMap(p=>(p.variants||[]).map(v=>({...v,product:p})))}
          columns={[
            {header:"Product", cell:r=><span className="font-semibold">{r.product.name}</span>},
            {header:"Variant SKU", cell:r=><span className="font-mono text-xs">{r.sku}</span>},
            {header:"Color/Size", cell:r=>`${r.color||"-"} / ${r.size||"-"}`},
            {header:"Stock", cell:r=><span className="font-bold">{fmtNum(r.stock)}</span>},
            {header:"Cost", cell:r=>fmtIDR(r.cost)},
            {header:"Value", cell:r=>fmtIDR(Number(r.stock)*Number(r.cost))},
            {header:"Status", cell:r=><StatusPill status={Number(r.stock)===0?"out_of_stock":(Number(r.stock)<=Number(r.product.minimum_stock||0)?"low_stock":"ok")}/>},
            {header:"", cell:r=><Button variant="outline" onClick={()=>setAdjust({kind:"product",pid:r.product.id,sku:r.sku,qty:0,type:"adjustment",notes:""})} data-testid={`adjust-${r.sku}`}>Adjust</Button>},
          ]}/>
      )}
      {tab==="materials" && <Materials/>}
      {tab==="movements" && (
        <DataTable testid="movements-table" rows={movements}
          columns={[
            {header:"Date", cell:r=>new Date(r.date).toLocaleString("id-ID")},
            {header:"Target", cell:r=>r.target},
            {header:"Ref", cell:r=><span className="font-mono text-xs">{r.ref_type}</span>},
            {header:"Type", cell:r=><StatusPill status={r.type==="sales"||r.type==="production"&&r.quantity<0?"processing":"ok"}/>},
            {header:"Qty", cell:r=><span className={r.quantity<0?"text-rose-600 font-bold":"text-emerald-600 font-bold"}>{r.quantity>0?"+":""}{fmtNum(r.quantity)}</span>},
            {header:"Before → After", cell:r=>`${fmtNum(r.before)} → ${fmtNum(r.after)}`},
            {header:"Notes", cell:r=><span className="text-xs text-muted-foreground">{r.notes||"-"}</span>},
          ]}/>
      )}
      {adjust && <Modal open onClose={()=>setAdjust(null)} title="Adjust Stok">
        <div className="space-y-3">
          <Field label="Quantity (+/-)"><Input type="number" value={adjust.qty} onChange={e=>setAdjust({...adjust,qty:e.target.value})}/></Field>
          <Field label="Type"><Select value={adjust.type} onChange={e=>setAdjust({...adjust,type:e.target.value})}>
            <option value="adjustment">Adjustment</option><option value="damage">Damage</option>
            <option value="return">Return</option><option value="opname">Stock Opname</option>
          </Select></Field>
          <Field label="Notes"><Input value={adjust.notes} onChange={e=>setAdjust({...adjust,notes:e.target.value})}/></Field>
        </div>
        <div className="flex justify-end gap-2 mt-6"><Button variant="outline" onClick={()=>setAdjust(null)}>Batal</Button><Button onClick={doAdjust} data-testid="btn-confirm-adjust">Simpan</Button></div>
      </Modal>}
    </div>
  );
}

// Generic master data page
export function MasterDataPage({ endpoint, title, subtitle, fields }) {
  const { rows, save, remove } = useCRUD(endpoint);
  const [editing, setEditing] = useState(null);
  const emptyForm = Object.fromEntries(fields.map(f=>[f.key, f.type==="number"?0:""]));

  return (
    <div>
      <PageHeader title={title} subtitle={subtitle} action={
        <Button onClick={()=>setEditing(emptyForm)} data-testid={`btn-new-${endpoint}`}><Plus size={14} className="inline mr-1"/> Tambah</Button>
      }/>
      <DataTable
        testid={`${endpoint}-table`}
        columns={[
          ...fields.filter(f=>f.list!==false).map(f=>({ header:f.label, cell:r=>f.render?f.render(r):(r[f.key]||"-") })),
          { header:"", cell:r=>(
            <div className="flex gap-2">
              <button onClick={()=>setEditing(r)}><Edit size={14}/></button>
              <button onClick={()=>remove(r.id)}><Trash2 size={14} className="text-rose-500"/></button>
            </div>
          )},
        ]}
        rows={rows}
      />
      {editing && <Modal open onClose={()=>setEditing(null)} title={editing.id?"Edit":"Tambah"}>
        <div className="grid grid-cols-2 gap-4">
          {fields.map(f=>(
            <Field key={f.key} label={f.label}>
              {f.type==="select" ? (
                <Select value={editing[f.key]||""} onChange={e=>setEditing({...editing,[f.key]:e.target.value})}>
                  <option value="">-- Pilih --</option>
                  {f.options.map(o=><option key={o.value} value={o.value}>{o.label}</option>)}
                </Select>
              ) : (
                <Input type={f.type||"text"} value={editing[f.key]??""} onChange={e=>setEditing({...editing,[f.key]:f.type==="number"?Number(e.target.value):e.target.value})}/>
              )}
            </Field>
          ))}
        </div>
        <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-border">
          <Button variant="outline" onClick={()=>setEditing(null)}>Batal</Button>
          <Button onClick={async()=>{ if (await save(editing, editing.id)) setEditing(null); }} data-testid={`btn-save-${endpoint}`}>Simpan</Button>
        </div>
      </Modal>}
    </div>
  );
}

export function Suppliers() {
  return <MasterDataPage endpoint="suppliers" title="Suppliers" subtitle="Vendor & pemasok"
    fields={[
      {key:"name",label:"Nama"},{key:"contact",label:"Kontak"},{key:"phone",label:"Telepon"},
      {key:"email",label:"Email"},{key:"address",label:"Alamat"},{key:"lead_time_days",label:"Lead Time (hari)",type:"number"},
      {key:"notes",label:"Catatan"},
    ]}/>;
}

export function Customers() {
  return <MasterDataPage endpoint="customers" title="Customers" subtitle="CRM pelanggan"
    fields={[
      {key:"name",label:"Nama"},{key:"phone",label:"Telepon"},{key:"email",label:"Email"},
      {key:"address",label:"Alamat"},
      {key:"customer_type",label:"Type",type:"select",options:[
        {value:"new",label:"New"},{value:"returning",label:"Returning"},{value:"vip",label:"VIP"},
      ], render:r=><StatusPill status={r.customer_type||"new"}/>},
      {key:"total_orders",label:"Orders",type:"number",list:true,render:r=>fmtNum(r.total_orders||0)},
      {key:"total_spending",label:"Spending",type:"number",list:true,render:r=>fmtIDR(r.total_spending||0)},
    ]}/>;
}

export function Assets() {
  return <MasterDataPage endpoint="assets" title="Assets" subtitle="Peralatan & depresiasi"
    fields={[
      {key:"name",label:"Nama"},{key:"purchase_price",label:"Harga Beli",type:"number",render:r=>fmtIDR(r.purchase_price)},
      {key:"purchase_date",label:"Tanggal Beli"},{key:"useful_life_years",label:"Umur (tahun)",type:"number"},
      {key:"residual_value",label:"Nilai Residu",type:"number",render:r=>fmtIDR(r.residual_value)},
    ]}/>;
}
