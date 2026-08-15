import { useState, useEffect } from "react";
import { api, formatErr } from "@/lib/api";
import { toast } from "sonner";
import { Modal, Field, Input, Select, Button, useCRUD } from "./_shared";
import { CheckCircle2, ArrowRight, ArrowLeft, X } from "lucide-react";

const STEPS = ["Business", "Currency", "Capital", "Marketplace", "Product", "Opening Inventory", "Complete"];

export function useOnboardingStatus() {
  const [status, setStatus] = useState(null);
  useEffect(() => {
    api.get("/onboarding/status").then((r) => setStatus(r.data)).catch(() => setStatus({ setup_complete: false }));
  }, []);
  return status;
}

export default function OnboardingWizard({ onClose, forceOpen = false }) {
  const [step, setStep] = useState(0);
  const [form, setForm] = useState({
    business_name: "RdCloth",
    currency: "IDR",
    initial_capital: 4000000,
    account_name: "Kas Tunai",
    marketplace_name: "",
    marketplace_admin_fee: 0,
    product_name: "",
    product_sku: "",
    product_selling_price: 0,
    variant_sku: "",
    opening_stock: 0,
    opening_cost: 0,
  });
  const [saving, setSaving] = useState(false);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const finish = async () => {
    setSaving(true);
    try {
      // 1. business + capital
      await api.post("/onboarding/complete", {
        business_name: form.business_name,
        currency: form.currency,
        initial_capital: Number(form.initial_capital || 0),
        account_name: form.account_name,
      });
      // 2. marketplace (optional)
      if (form.marketplace_name) {
        await api.post("/marketplaces", { name: form.marketplace_name, admin_fee_pct: Number(form.marketplace_admin_fee || 0), service_fee_pct: 0, payment_fee_pct: 0 });
      }
      // 3. product (optional)
      if (form.product_name && form.product_sku) {
        await api.post("/products", {
          sku: form.product_sku, name: form.product_name, brand: form.business_name,
          cost: Number(form.opening_cost || 0), selling_price: Number(form.product_selling_price || 0),
          minimum_stock: 3, status: "active",
          variants: [{ sku: form.variant_sku || form.product_sku, color: "", size: "OS", stock: Number(form.opening_stock || 0), cost: Number(form.opening_cost || 0), selling_price: Number(form.product_selling_price || 0) }],
        });
      }
      toast.success("Setup selesai. Selamat datang di RdCloth!");
      setStep(STEPS.length - 1);
      setTimeout(() => { onClose?.(); window.location.reload(); }, 1500);
    } catch (e) {
      toast.error(formatErr(e.response?.data?.detail) || "Gagal menyimpan");
    } finally {
      setSaving(false);
    }
  };

  const next = () => setStep((s) => Math.min(STEPS.length - 1, s + 1));
  const back = () => setStep((s) => Math.max(0, s - 1));

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" data-testid="onboarding-wizard">
      <div className="w-full max-w-2xl bg-card border border-border rounded-lg shadow-2xl overflow-hidden">
        {/* header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div>
            <div className="text-[10px] uppercase font-bold tracking-[0.25em] text-muted-foreground">Setup Wizard · Step {step + 1} / {STEPS.length}</div>
            <h3 className="font-display font-bold text-xl tracking-tight">{STEPS[step]}</h3>
          </div>
          {!forceOpen && <button onClick={onClose} data-testid="wizard-close"><X size={18} /></button>}
        </div>
        {/* progress */}
        <div className="px-6 pt-4">
          <div className="h-1 bg-stone-200 dark:bg-stone-800 rounded-full overflow-hidden">
            <div className="h-full bg-neutral-900 dark:bg-stone-100 transition-all" style={{ width: `${((step + 1) / STEPS.length) * 100}%` }} />
          </div>
        </div>
        {/* body */}
        <div className="p-6 min-h-[280px]">
          {step === 0 && (
            <div className="space-y-3" data-testid="step-business">
              <p className="text-sm text-muted-foreground mb-4">Kenali bisnismu — masukkan nama brand yang akan tampil di seluruh aplikasi.</p>
              <Field label="Nama Bisnis"><Input value={form.business_name} onChange={(e) => set("business_name", e.target.value)} data-testid="wiz-business-name" /></Field>
            </div>
          )}
          {step === 1 && (
            <div className="space-y-3" data-testid="step-currency">
              <p className="text-sm text-muted-foreground mb-4">Pilih mata uang default untuk semua transaksi.</p>
              <Field label="Currency">
                <Select value={form.currency} onChange={(e) => set("currency", e.target.value)}>
                  <option value="IDR">IDR — Rupiah</option>
                  <option value="USD">USD — Dollar</option>
                  <option value="MYR">MYR — Ringgit</option>
                </Select>
              </Field>
            </div>
          )}
          {step === 2 && (
            <div className="space-y-3" data-testid="step-capital">
              <p className="text-sm text-muted-foreground mb-4">Masukkan modal awal — ini akan tercatat sebagai Owner Investment (bukan revenue).</p>
              <Field label="Initial Capital"><Input type="number" value={form.initial_capital} onChange={(e) => set("initial_capital", e.target.value)} data-testid="wiz-capital" /></Field>
              <Field label="Account Name (cash/bank)"><Input value={form.account_name} onChange={(e) => set("account_name", e.target.value)} /></Field>
            </div>
          )}
          {step === 3 && (
            <div className="space-y-3" data-testid="step-marketplace">
              <p className="text-sm text-muted-foreground mb-4">Tambahkan marketplace utama (opsional — Anda bisa menambah lebih banyak nanti).</p>
              <Field label="Marketplace Name (opsional)"><Input placeholder="Shopee / TikTok Shop / WhatsApp" value={form.marketplace_name} onChange={(e) => set("marketplace_name", e.target.value)} /></Field>
              <Field label="Admin Fee %"><Input type="number" step="0.01" value={form.marketplace_admin_fee} onChange={(e) => set("marketplace_admin_fee", e.target.value)} /></Field>
            </div>
          )}
          {step === 4 && (
            <div className="space-y-3" data-testid="step-product">
              <p className="text-sm text-muted-foreground mb-4">Tambahkan produk pertama Anda (opsional).</p>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Product Name"><Input value={form.product_name} onChange={(e) => set("product_name", e.target.value)} placeholder="RdBasic T-Shirt" /></Field>
                <Field label="SKU"><Input value={form.product_sku} onChange={(e) => set("product_sku", e.target.value)} placeholder="RDB-001" /></Field>
                <Field label="Selling Price"><Input type="number" value={form.product_selling_price} onChange={(e) => set("product_selling_price", e.target.value)} /></Field>
                <Field label="Variant SKU"><Input value={form.variant_sku} onChange={(e) => set("variant_sku", e.target.value)} placeholder="RDB-BL-M" /></Field>
              </div>
            </div>
          )}
          {step === 5 && (
            <div className="space-y-3" data-testid="step-inventory">
              <p className="text-sm text-muted-foreground mb-4">Berapa stok awal & modalnya untuk produk di atas?</p>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Opening Stock (pcs)"><Input type="number" value={form.opening_stock} onChange={(e) => set("opening_stock", e.target.value)} /></Field>
                <Field label="Cost per Unit"><Input type="number" value={form.opening_cost} onChange={(e) => set("opening_cost", e.target.value)} /></Field>
              </div>
            </div>
          )}
          {step === 6 && (
            <div className="text-center py-8" data-testid="step-complete">
              <div className="w-16 h-16 rounded-full bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 flex items-center justify-center mx-auto mb-4">
                <CheckCircle2 size={32} strokeWidth={1.5} />
              </div>
              <h3 className="font-display font-black text-2xl tracking-tighter mb-2">Setup Ready!</h3>
              <p className="text-sm text-muted-foreground max-w-sm mx-auto">Klik <b>Selesai</b> untuk menyimpan konfigurasi awal Anda. Anda bisa mengubah semuanya di Settings kapan saja.</p>
            </div>
          )}
        </div>
        {/* footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-border bg-stone-50 dark:bg-stone-900">
          <Button variant="outline" onClick={back} disabled={step === 0} data-testid="wiz-back"><ArrowLeft size={14} className="inline mr-1" /> Kembali</Button>
          {step < STEPS.length - 1 && <Button onClick={next} data-testid="wiz-next">Lanjut <ArrowRight size={14} className="inline ml-1" /></Button>}
          {step === STEPS.length - 1 && <Button onClick={finish} disabled={saving} data-testid="wiz-finish">{saving ? "Menyimpan..." : "Selesai"}</Button>}
        </div>
      </div>
    </div>
  );
}
