import { useState } from "react";
import { PageHeader, DataTable, Modal, Field, Input, Select, Button, StatusPill, useCRUD, Plus, Edit, Trash2 } from "./_shared";
import { fmtIDR, fmtNum } from "@/lib/api";

export default function Products() {
  const { rows, save, remove } = useCRUD("products");
  const { rows: cats } = useCRUD("categories");
  const [editing, setEditing] = useState(null);

  const openNew = () => setEditing({ variants: [{ color:"Black", size:"M", stock:0, cost:0, selling_price:0, sku:"" }] });

  return (
    <div>
      <PageHeader title="Products" subtitle="Katalog produk" action={
        <Button onClick={openNew} data-testid="btn-new-product"><Plus size={14} className="inline mr-1"/> Produk Baru</Button>
      }/>
      <DataTable
        testid="products-table"
        columns={[
          { header: "SKU", cell: r => <span className="font-mono text-xs">{r.sku}</span> },
          { header: "Name", cell: r => <span className="font-semibold">{r.name}</span> },
          { header: "Category", cell: r => cats.find(c=>c.id===r.category_id)?.name || "-" },
          { header: "Variants", cell: r => fmtNum((r.variants||[]).length) },
          { header: "Total Stock", cell: r => fmtNum((r.variants||[]).reduce((s,v)=>s+Number(v.stock||0),0)) },
          { header: "Selling Price", cell: r => fmtIDR(r.selling_price) },
          { header: "Status", cell: r => <StatusPill status={r.status||"active"} /> },
          { header: "", cell: r => (
            <div className="flex gap-2">
              <button onClick={() => setEditing(r)} data-testid={`edit-product-${r.id}`}><Edit size={14}/></button>
              <button onClick={() => remove(r.id)} data-testid={`delete-product-${r.id}`}><Trash2 size={14} className="text-rose-500"/></button>
            </div>
          )},
        ]}
        rows={rows}
      />
      {editing && <ProductForm data={editing} cats={cats} onClose={() => setEditing(null)} onSave={async (d) => { const ok = await save(d, editing.id); if (ok) setEditing(null); }} />}
    </div>
  );
}

function ProductForm({ data, cats, onClose, onSave }) {
  const [form, setForm] = useState({
    sku: "", name: "", category_id: "", brand: "RdCloth", material: "", cost: 0, selling_price: 0, minimum_stock: 3, status: "active", image_url: "",
    ...data,
    variants: data.variants || [{ color:"", size:"", stock:0, cost:0, selling_price:0, sku:"" }],
  });
  const set = (k,v) => setForm(f => ({...f,[k]:v}));
  const setVariant = (i,k,v) => setForm(f => ({...f, variants: f.variants.map((x,idx)=>idx===i?{...x,[k]:v}:x)}));
  const addVar = () => setForm(f => ({...f, variants: [...f.variants, { color:"", size:"", stock:0, cost:form.cost, selling_price:form.selling_price, sku:"" }]}));
  const rmVar = (i) => setForm(f => ({...f, variants: f.variants.filter((_,idx)=>idx!==i)}));

  return (
    <Modal open onClose={onClose} title={data.id ? "Edit Produk" : "Produk Baru"}>
      <div className="grid grid-cols-2 gap-4">
        <Field label="SKU"><Input data-testid="product-sku" value={form.sku} onChange={e=>set("sku",e.target.value)} /></Field>
        <Field label="Nama"><Input data-testid="product-name" value={form.name} onChange={e=>set("name",e.target.value)} /></Field>
        <Field label="Kategori">
          <Select data-testid="product-category" value={form.category_id} onChange={e=>set("category_id",e.target.value)}>
            <option value="">-- Pilih --</option>
            {cats.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </Select>
        </Field>
        <Field label="Brand"><Input value={form.brand} onChange={e=>set("brand",e.target.value)} /></Field>
        <Field label="Material"><Input value={form.material} onChange={e=>set("material",e.target.value)} /></Field>
        <Field label="Image URL"><Input value={form.image_url} onChange={e=>set("image_url",e.target.value)} /></Field>
        <Field label="Cost (default)"><Input type="number" value={form.cost} onChange={e=>set("cost",e.target.value)} /></Field>
        <Field label="Selling Price"><Input type="number" value={form.selling_price} onChange={e=>set("selling_price",e.target.value)} /></Field>
        <Field label="Minimum Stock"><Input type="number" value={form.minimum_stock} onChange={e=>set("minimum_stock",e.target.value)} /></Field>
        <Field label="Status">
          <Select value={form.status} onChange={e=>set("status",e.target.value)}>
            <option value="active">Active</option><option value="inactive">Inactive</option>
          </Select>
        </Field>
      </div>

      <div className="mt-6">
        <div className="flex items-center justify-between mb-2">
          <div className="text-[10px] uppercase font-bold tracking-widest text-muted-foreground">Variants</div>
          <Button variant="outline" onClick={addVar} data-testid="add-variant">+ Variant</Button>
        </div>
        <div className="space-y-2">
          {form.variants.map((v, i) => (
            <div key={i} className="grid grid-cols-6 gap-2 items-end">
              <Field label="Color"><Input value={v.color} onChange={e=>setVariant(i,"color",e.target.value)} /></Field>
              <Field label="Size"><Input value={v.size} onChange={e=>setVariant(i,"size",e.target.value)} /></Field>
              <Field label="SKU"><Input value={v.sku} onChange={e=>setVariant(i,"sku",e.target.value)} placeholder="auto" /></Field>
              <Field label="Stock"><Input type="number" value={v.stock} onChange={e=>setVariant(i,"stock",e.target.value)} /></Field>
              <Field label="Cost"><Input type="number" value={v.cost} onChange={e=>setVariant(i,"cost",e.target.value)} /></Field>
              <div className="flex gap-1">
                <Field label="Price"><Input type="number" value={v.selling_price} onChange={e=>setVariant(i,"selling_price",e.target.value)} /></Field>
                <button onClick={()=>rmVar(i)} className="text-rose-500 pb-2"><Trash2 size={14}/></button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-border">
        <Button variant="outline" onClick={onClose}>Batal</Button>
        <Button onClick={() => onSave(form)} data-testid="btn-save-product">Simpan</Button>
      </div>
    </Modal>
  );
}
