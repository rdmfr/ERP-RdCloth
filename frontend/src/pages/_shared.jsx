import { useCallback, useEffect, useState } from "react";
import { api, fmtIDR, fmtNum, formatErr } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Edit, Trash2, X } from "lucide-react";

export function PageHeader({ title, subtitle, action }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
      <div>
        <div className="text-[10px] uppercase font-bold tracking-[0.25em] text-muted-foreground">{subtitle}</div>
        <h1 className="font-display font-black text-3xl sm:text-4xl tracking-tighter">{title}</h1>
      </div>
      {action}
    </div>
  );
}

export function Modal({ open, onClose, title, children }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="w-full max-w-2xl bg-card border border-border rounded-lg shadow-lg max-h-[90vh] overflow-hidden flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between p-5 border-b border-border">
          <h3 className="font-display font-bold text-lg tracking-tight">{title}</h3>
          <button onClick={onClose} data-testid="modal-close"><X size={18} /></button>
        </div>
        <div className="p-5 overflow-y-auto scroll-thin">{children}</div>
      </div>
    </div>
  );
}

export function Field({ label, children }) {
  return (
    <div>
      <label className="text-[10px] uppercase font-bold tracking-widest text-muted-foreground">{label}</label>
      <div className="mt-1">{children}</div>
    </div>
  );
}

export function Input(props) {
  return <input {...props} className={`w-full px-3 py-2 bg-background border border-border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-neutral-900 dark:focus:ring-stone-100 ${props.className||""}`} />;
}

export function Select({ children, ...p }) {
  return <select {...p} className={`w-full px-3 py-2 bg-background border border-border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-neutral-900 dark:focus:ring-stone-100 ${p.className||""}`}>{children}</select>;
}

export function Button({ variant="primary", ...p }) {
  const styles = {
    primary: "bg-neutral-900 text-white dark:bg-stone-100 dark:text-stone-900 hover:opacity-90",
    outline: "border border-border hover:bg-stone-100 dark:hover:bg-stone-900",
    danger: "bg-rose-600 text-white hover:bg-rose-700",
  };
  return <button {...p} className={`px-4 py-2 rounded-md text-sm font-semibold transition-colors disabled:opacity-50 ${styles[variant]} ${p.className||""}`} />;
}

export function DataTable({ columns, rows, empty = "Belum ada data", testid }) {
  return (
    <div className="rounded-lg border border-border bg-card overflow-x-auto scroll-thin" data-testid={testid}>
      <table className="w-full text-sm">
        <thead className="bg-stone-100 dark:bg-stone-900 text-[10px] uppercase tracking-widest text-muted-foreground">
          <tr>{columns.map((c, i) => <th key={i} className="text-left px-4 py-3 font-semibold whitespace-nowrap">{c.header}</th>)}</tr>
        </thead>
        <tbody>
          {rows.length === 0 && <tr><td colSpan={columns.length} className="text-center py-12 text-muted-foreground">{empty}</td></tr>}
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-border hover:bg-stone-50 dark:hover:bg-stone-900/50">
              {columns.map((c, j) => <td key={j} className="px-4 py-3">{c.cell(r)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function StatusPill({ status }) {
  const map = {
    active: "bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-400",
    inactive: "bg-stone-100 text-stone-700 border-stone-200 dark:bg-stone-800 dark:text-stone-400",
    paid: "bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-400",
    unpaid: "bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400",
    pending: "bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400",
    processing: "bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-900/30 dark:text-blue-400",
    completed: "bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-400",
    received: "bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-400",
    cancelled: "bg-rose-100 text-rose-800 border-rose-200 dark:bg-rose-900/30 dark:text-rose-400",
    draft: "bg-stone-100 text-stone-700 border-stone-200 dark:bg-stone-800 dark:text-stone-400",
    ordered: "bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-900/30 dark:text-blue-400",
    in_production: "bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-900/30 dark:text-blue-400",
    vip: "bg-purple-100 text-purple-800 border-purple-200 dark:bg-purple-900/30 dark:text-purple-400",
    returning: "bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-900/30 dark:text-blue-400",
    new: "bg-stone-100 text-stone-700 border-stone-200 dark:bg-stone-800 dark:text-stone-400",
    low_stock: "bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-900/30 dark:text-amber-400",
    out_of_stock: "bg-rose-100 text-rose-800 border-rose-200 dark:bg-rose-900/30 dark:text-rose-400",
    ok: "bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-400",
  };
  const cls = map[status] || map.draft;
  return <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-widest border ${cls}`}>{String(status||"").replace("_"," ")}</span>;
}

// Simple CRUD page factory for master data
export function useCRUD(endpoint) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const reload = useCallback(async () => {
    setLoading(true);
    try { const r = await api.get(`/${endpoint}`); setRows(r.data); }
    catch (e) { toast.error(formatErr(e.response?.data?.detail)); }
    finally { setLoading(false); }
  }, [endpoint]);
  useEffect(() => { reload(); }, [reload]);
  const save = async (data, id) => {
    try {
      if (id) await api.put(`/${endpoint}/${id}`, data);
      else await api.post(`/${endpoint}`, data);
      toast.success("Tersimpan");
      await reload();
      return true;
    } catch (e) { toast.error(formatErr(e.response?.data?.detail)); return false; }
  };
  const remove = async (id) => {
    if (!confirm("Hapus data ini?")) return;
    try { await api.delete(`/${endpoint}/${id}`); toast.success("Terhapus"); await reload(); }
    catch (e) { toast.error(formatErr(e.response?.data?.detail)); }
  };
  return { rows, loading, reload, save, remove };
}

export { Plus, Edit, Trash2 };
