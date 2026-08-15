import { useState } from "react";
import { PageHeader, Field, Input, Select, Button, DataTable, StatusPill, useCRUD } from "./_shared";
import { api, fmtIDR, formatErr } from "@/lib/api";
import { toast } from "sonner";
import { Upload, Download, ClipboardPaste, AlertCircle } from "lucide-react";

const SAMPLE_CSV = `order_number,date,customer_name,sales_channel,variant_sku,quantity,selling_price,discount,shipping,marketplace_fee,advertising_cost
SP-2026-0001,2026-08-14,Rina Sari,Shopee,RDB-BL-M,2,89000,0,10000,15575,3000
SP-2026-0002,2026-08-13,Budi Santoso,Shopee,RDB-WH-L,1,89000,5000,10000,7788,3000
TT-2026-0001,2026-08-12,Andi Wijaya,TikTok Shop,RDC-BL-M,1,109000,0,10000,8720,3000`;

// Parse CSV / TSV / paste text into array of objects
function parsePaste(text) {
  if (!text.trim()) return [];
  const sep = text.includes("\t") ? "\t" : ",";
  const lines = text.trim().split(/\r?\n/);
  const header = lines[0].split(sep).map((h) => h.trim());
  return lines.slice(1).map((line) => {
    // basic CSV split (no quote handling — for simple paste)
    const cells = line.split(sep);
    const obj = {};
    header.forEach((h, i) => { obj[h] = (cells[i] || "").trim(); });
    return obj;
  });
}

export default function MarketplaceImport() {
  const [text, setText] = useState("");
  const [parsed, setParsed] = useState([]);
  const [result, setResult] = useState(null);
  const [importing, setImporting] = useState(false);
  const { rows: products } = useCRUD("products");

  const allSkus = products.flatMap((p) => (p.variants || []).map((v) => ({ sku: v.sku, name: `${p.name} (${v.color}/${v.size})`, stock: v.stock })));

  const doParse = () => {
    try {
      const arr = parsePaste(text);
      setParsed(arr);
      setResult(null);
      toast.success(`Preview ${arr.length} baris`);
    } catch {
      toast.error("Format tidak dikenali. Pastikan header CSV valid.");
    }
  };

  const doImport = async () => {
    if (parsed.length === 0) return;
    setImporting(true);
    try {
      const orders = parsed.map((r) => ({
        order_number: r.order_number || undefined,
        date: r.date ? new Date(r.date).toISOString() : undefined,
        customer_name: r.customer_name || "Marketplace Buyer",
        sales_channel: r.sales_channel || "Shopee",
        variant_sku: r.variant_sku,
        quantity: Number(r.quantity || 1),
        selling_price: Number(r.selling_price || 0),
        discount: Number(r.discount || 0),
        shipping: Number(r.shipping || 0),
        marketplace_fee: Number(r.marketplace_fee || 0),
        advertising_cost: Number(r.advertising_cost || 0),
      }));
      const { data } = await api.post("/marketplace/import", { orders });
      setResult(data);
      toast.success(`${data.created} order berhasil diimpor`);
    } catch (e) {
      toast.error(formatErr(e.response?.data?.detail) || "Gagal import");
    } finally {
      setImporting(false);
    }
  };

  const downloadSample = () => {
    const blob = new Blob([SAMPLE_CSV], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = "rdcloth_import_template.csv"; a.click(); URL.revokeObjectURL(url);
  };

  return (
    <div>
      <PageHeader title="Marketplace Import" subtitle="Import orders dari Shopee, TikTok Shop, dll" action={
        <Button variant="outline" onClick={downloadSample} data-testid="download-template"><Download size={14} className="inline mr-1" /> Download Template</Button>
      } />

      <div className="grid lg:grid-cols-2 gap-4">
        <div className="p-6 rounded-lg border border-border bg-card">
          <div className="flex items-center gap-2 mb-4">
            <ClipboardPaste size={18} className="text-muted-foreground" />
            <h3 className="font-display font-bold text-lg tracking-tight">Paste CSV Data</h3>
          </div>
          <div className="text-xs text-muted-foreground mb-2 leading-relaxed">
            Export orders dari Shopee Seller Center atau TikTok Shop Center sebagai CSV, lalu paste isinya di sini. Kolom wajib: <code className="bg-stone-100 dark:bg-stone-900 px-1 rounded">variant_sku, quantity, selling_price</code>. Kolom opsional: <code className="bg-stone-100 dark:bg-stone-900 px-1 rounded">order_number, date, customer_name, sales_channel, discount, shipping, marketplace_fee, advertising_cost</code>.
          </div>
          <textarea
            data-testid="import-textarea"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={SAMPLE_CSV}
            rows={12}
            className="w-full px-3 py-2 bg-background border border-border rounded-md text-xs font-mono focus:outline-none focus:ring-2 focus:ring-neutral-900 dark:focus:ring-stone-100"
          />
          <div className="flex gap-2 mt-3">
            <Button variant="outline" onClick={() => setText(SAMPLE_CSV)} data-testid="load-sample">Load Sample</Button>
            <Button onClick={doParse} data-testid="parse-btn">Preview <Upload size={14} className="inline ml-1" /></Button>
          </div>
        </div>

        <div className="p-6 rounded-lg border border-border bg-card">
          <h3 className="font-display font-bold text-lg tracking-tight mb-4">Available Variants ({allSkus.length})</h3>
          <div className="max-h-80 overflow-y-auto scroll-thin">
            <table className="w-full text-xs">
              <thead className="text-[10px] uppercase text-muted-foreground sticky top-0 bg-card"><tr><th className="text-left py-2">SKU</th><th className="text-left py-2">Product</th><th className="text-right py-2">Stock</th></tr></thead>
              <tbody>
                {allSkus.map((v) => (
                  <tr key={v.sku} className="border-t border-border"><td className="py-1.5 font-mono">{v.sku}</td><td className="py-1.5">{v.name}</td><td className="py-1.5 text-right font-semibold">{v.stock}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {parsed.length > 0 && (
        <div className="mt-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-display font-bold text-lg tracking-tight">Preview ({parsed.length} orders)</h3>
            <Button onClick={doImport} disabled={importing} data-testid="import-btn">{importing ? "Importing..." : `Import ${parsed.length} Orders`}</Button>
          </div>
          <DataTable testid="import-preview" rows={parsed} columns={[
            { header: "Order #", cell: (r) => r.order_number || "(auto)" },
            { header: "Date", cell: (r) => r.date || "-" },
            { header: "Channel", cell: (r) => r.sales_channel },
            { header: "SKU", cell: (r) => <span className="font-mono text-xs">{r.variant_sku}</span> },
            { header: "Qty", cell: (r) => r.quantity },
            { header: "Price", cell: (r) => fmtIDR(r.selling_price) },
            { header: "MP Fee", cell: (r) => <span className="text-rose-600">{fmtIDR(r.marketplace_fee)}</span> },
            { header: "Match", cell: (r) => allSkus.find((s) => s.sku === r.variant_sku) ? <StatusPill status="ok" /> : <StatusPill status="out_of_stock" /> },
          ]} />
        </div>
      )}

      {result && (
        <div className="mt-6 p-6 rounded-lg border border-border bg-card">
          <h3 className="font-display font-bold text-lg tracking-tight mb-3">Import Result</h3>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div className="p-4 rounded-md bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-900/30">
              <div className="text-[10px] uppercase font-bold tracking-widest text-emerald-800 dark:text-emerald-400">Created</div>
              <div className="kpi-value text-3xl text-emerald-700 dark:text-emerald-400">{result.created}</div>
            </div>
            <div className="p-4 rounded-md bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-900/30">
              <div className="text-[10px] uppercase font-bold tracking-widest text-amber-800 dark:text-amber-400">Skipped</div>
              <div className="kpi-value text-3xl text-amber-700 dark:text-amber-400">{result.skipped.length}</div>
            </div>
          </div>
          {result.skipped.length > 0 && (
            <div className="space-y-1 text-sm">
              <div className="text-[10px] uppercase font-bold tracking-widest text-muted-foreground mb-1">Skipped rows</div>
              {result.skipped.map((s, i) => (
                <div key={i} className="flex items-center gap-2 text-amber-800 dark:text-amber-400"><AlertCircle size={12} /> <span className="font-mono">{s.sku}</span> — {s.reason}</div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
