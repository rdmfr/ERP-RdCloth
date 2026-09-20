import { useState, useMemo, useRef } from "react";
import { PageHeader, Button, DataTable } from "./_shared";
import { api, fmtIDR, formatErr } from "@/lib/api";
import { toast } from "sonner";
import {
  Upload, Download, ClipboardPaste, CheckCircle2, XCircle, AlertTriangle,
  RotateCcw, FileSpreadsheet, Layers, ShoppingBag, Users, Truck, Wallet,
  ArrowRight, ShieldCheck, HelpCircle
} from "lucide-react";
import { useNavigate } from "react-router-dom";

const MODULES = [
  { id: "sales_orders", label: "Order Marketplace & Penjualan", icon: ShoppingBag, targetRoute: "/sales", desc: "Import transaksi penjualan Shopee, TikTok Shop, WhatsApp, Offline" },
  { id: "products", label: "Master Produk & Varian", icon: Layers, targetRoute: "/products", desc: "Import katalog produk, varian SKU, harga jual, dan stok awal" },
  { id: "materials", label: "Master Bahan Baku", icon: Layers, targetRoute: "/materials", desc: "Import bahan baku, satuan, biaya (cost), dan stok persediaan" },
  { id: "customers", label: "Data Pelanggan", icon: Users, targetRoute: "/customers", desc: "Import database customer, nomor HP, email, dan alamat" },
  { id: "suppliers", label: "Data Supplier", icon: Truck, targetRoute: "/suppliers", desc: "Import daftar vendor, supplier kain, sablon, aksesoris" },
  { id: "opening_balance", label: "Saldo Awal Akun COA", icon: Wallet, targetRoute: "/finance-suite", desc: "Import saldo awal kas, bank, piutang, hutang, dan ekuitas awal" },
];

const SAMPLE_DATA = {
  sales_orders: `order_number,date,customer_name,sales_channel,variant_sku,quantity,selling_price,discount,shipping,marketplace_fee,advertising_cost
SP-2026-0001,2026-08-14,Rina Sari,Shopee,RDB-BL-M,2,89000,0,10000,15575,3000
SP-2026-0002,2026-08-13,Budi Santoso,Shopee,RDB-WH-L,1,89000,5000,10000,7788,3000
TT-2026-0001,2026-08-12,Andi Wijaya,TikTok Shop,RDC-BL-M,1,109000,0,10000,8720,3000`,
  products: `name,sku,category,selling_price,cost,stock,color,size,min_stock
Kaos Polos Heavyweight 24s,KPH-BLK-M,Kaos,95000,50000,40,Hitam,M,10
Kaos Polos Heavyweight 24s,KPH-BLK-L,Kaos,95000,50000,35,Hitam,L,10
Kemeja Flanel Kotak,FLN-RED-XL,Kemeja,145000,80000,20,Merah,XL,5`,
  materials: `name,sku,category,unit,cost,stock,min_stock
Kain Katun Bambu Hitam,RAW-KB-BLK,Kain,kg,125000,30,5
Kancing Batok Kelapa 18L,RAW-KNC-BTK,Aksesoris,gross,35000,20,3
Plastik Polymailer 25x35,RAW-PLY-2535,Packaging,pcs,450,500,100`,
  customers: `name,phone,email,address,customer_type
Budi Santoso,081234567890,budi@example.com,Jl. Sudirman No. 10 Jakarta,vip
Siti Nurhaliza,082345678901,siti@example.com,Jl. Merdeka No. 45 Bandung,new
Andi Wijaya,085678901234,andi@example.com,Jl. Diponegoro No. 8 Surabaya,returning`,
  suppliers: `name,contact_name,phone,email,address
CV Tekstil Maju Jaya,Pak Hendra,081122334455,hendra@tekstilmaju.com,Kawasan Industri Cimahi Bandung
PT Label Cemerlang,Ibu Maya,082233445566,maya@labelcemerlang.com,Jl. Rungkut Surabaya`,
  opening_balance: `account_code,debit,credit
1-10001,25000000,0
1-10002,50000000,0
2-10100,0,15000000
3-10000,0,60000000`,
};

function parseCSVLine(text, delimiter) {
  const result = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    const nextChar = text[i + 1];
    if (char === '"' || char === "'") {
      if (inQuotes && nextChar === char) {
        cur += char;
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (char === delimiter && !inQuotes) {
      result.push(cur.trim());
      cur = "";
    } else {
      cur += char;
    }
  }
  result.push(cur.trim());
  return result;
}

function parseCSV(text) {
  if (!text || !text.trim()) return [];
  const lines = text.trim().split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (lines.length < 2) return [];

  const firstLine = lines[0];
  let delimiter = ",";
  if (firstLine.includes("\t")) delimiter = "\t";
  else if (firstLine.includes(";")) delimiter = ";";

  const headers = parseCSVLine(firstLine, delimiter).map((h) => h.replace(/^["']|["']$/g, "").trim().toLowerCase());

  return lines.slice(1).map((line) => {
    const cells = parseCSVLine(line, delimiter);
    const obj = {};
    headers.forEach((h, i) => {
      let val = cells[i] !== undefined ? cells[i] : "";
      val = val.replace(/^["']|["']$/g, "").trim();
      obj[h] = val;
    });
    return obj;
  });
}

export default function MarketplaceImport() {
  const [selectedModule, setSelectedModule] = useState("sales_orders");
  const [rawText, setRawText] = useState("");
  const [validationResult, setValidationResult] = useState(null);
  const [isValidating, setIsValidating] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [allowPartial, setAllowPartial] = useState(false);
  const [importSummary, setImportSummary] = useState(null);
  const fileInputRef = useRef(null);
  const navigate = useNavigate();

  const currentModObj = useMemo(() => MODULES.find((m) => m.id === selectedModule) || MODULES[0], [selectedModule]);

  const handleSelectModule = (modId) => {
    setSelectedModule(modId);
    setRawText("");
    setValidationResult(null);
    setImportSummary(null);
  };

  const handleLoadSample = () => {
    const sample = SAMPLE_DATA[selectedModule] || "";
    setRawText(sample);
    setValidationResult(null);
    setImportSummary(null);
    toast.info(`Contoh data untuk ${currentModObj.label} dimuat`);
  };

  const handleDownloadTemplate = () => {
    const link = document.createElement("a");
    link.href = `/api/imports/templates/${selectedModule}`;
    link.download = `template_${selectedModule}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast.success(`Template ${currentModObj.label} diunduh`);
  };

  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      const content = evt.target?.result;
      if (typeof content === "string") {
        setRawText(content);
        setValidationResult(null);
        setImportSummary(null);
        toast.success(`File ${file.name} berhasil dibaca`);
      }
    };
    reader.readAsText(file);
    e.target.value = "";
  };

  const handlePreviewValidation = async () => {
    const parsedRows = parseCSV(rawText);
    if (parsedRows.length === 0) {
      toast.error("Format data kosong atau header tidak valid. Pastikan ada minimal 1 baris header dan 1 baris data.");
      return;
    }

    setIsValidating(true);
    try {
      const { data } = await api.post("/imports/preview", {
        kind: selectedModule,
        rows: parsedRows,
      });
      setValidationResult(data);
      setImportSummary(null);
      if (data.is_all_valid) {
        toast.success(`Semua ${data.total} baris valid dan siap diimpor!`);
      } else {
        toast.warning(`${data.invalid_count} dari ${data.total} baris memiliki kesalahan.`);
      }
    } catch (err) {
      toast.error(formatErr(err.response?.data?.detail) || "Gagal melakukan validasi data.");
    } finally {
      setIsValidating(false);
    }
  };

  const handleExecuteImport = async () => {
    if (!validationResult || validationResult.rows.length === 0) {
      toast.error("Lakukan preview & validasi data terlebih dahulu.");
      return;
    }

    if (!allowPartial && !validationResult.is_all_valid) {
      toast.error("Mode Ketat Aktif: Perbaiki semua baris error sebelum melanjutkan, atau aktifkan 'Import Baris Valid Saja'.");
      return;
    }

    setIsImporting(true);
    try {
      const rawRows = validationResult.rows.map((r) => r.raw);
      const { data } = await api.post("/imports/execute", {
        kind: selectedModule,
        rows: rawRows,
        allow_partial: allowPartial,
      });

      setImportSummary(data);
      toast.success(`Berhasil mengimpor ${data.created || 0} data ke sistem!`);
      setValidationResult(null);
      setRawText("");
    } catch (err) {
      toast.error(formatErr(err.response?.data?.detail) || "Eksekusi import gagal dan transaksi dibatalkan.");
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Universal Data Import Wizard"
        subtitle="Import Data Cepat, Preview Realtime & Proteksi Rollback"
        action={
          <div className="flex items-center gap-2">
            <input
              type="file"
              ref={fileInputRef}
              accept=".csv,.txt,.tsv"
              className="hidden"
              onChange={handleFileUpload}
            />
            <Button variant="outline" onClick={() => fileInputRef.current?.click()} data-testid="upload-file-btn">
              <Upload size={14} className="inline mr-1" /> Unggah File CSV
            </Button>
            <Button variant="outline" onClick={handleDownloadTemplate} data-testid="download-template-btn">
              <Download size={14} className="inline mr-1" /> Download Template
            </Button>
          </div>
        }
      />

      {/* Module Selector Tabs */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
        {MODULES.map((m) => {
          const Icon = m.icon;
          const isSelected = selectedModule === m.id;
          return (
            <button
              key={m.id}
              onClick={() => handleSelectModule(m.id)}
              className={`flex flex-col items-start p-3 rounded-lg border text-left transition-all ${
                isSelected
                  ? "border-neutral-900 bg-neutral-900 text-white dark:border-stone-100 dark:bg-stone-100 dark:text-stone-900 shadow-sm"
                  : "border-border bg-card text-foreground hover:bg-stone-100 dark:hover:bg-stone-900/60"
              }`}
              data-testid={`module-tab-${m.id}`}
            >
              <div className="flex items-center justify-between w-full mb-1">
                <Icon size={16} />
                {isSelected && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />}
              </div>
              <div className="font-semibold text-xs leading-snug">{m.label}</div>
            </button>
          );
        })}
      </div>

      {/* Import Form & Instructions */}
      <div className="grid lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <div className="p-5 rounded-lg border border-border bg-card">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
              <div className="flex items-center gap-2">
                <ClipboardPaste size={18} className="text-muted-foreground" />
                <h3 className="font-display font-bold text-base tracking-tight">
                  Tempel (Paste) atau Edit CSV Data
                </h3>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={handleLoadSample} data-testid="load-sample-btn" className="text-xs py-1.5 px-3">
                  <RotateCcw size={13} className="inline mr-1" /> Isi Contoh Data
                </Button>
              </div>
            </div>

            <textarea
              data-testid="import-textarea"
              value={rawText}
              onChange={(e) => {
                setRawText(e.target.value);
                setValidationResult(null);
                setImportSummary(null);
              }}
              placeholder={`Salin dan tempel data CSV atau TSV di sini...\nContoh:\n${SAMPLE_DATA[selectedModule] || ""}`}
              rows={11}
              className="w-full px-3 py-2 bg-background border border-border rounded-md text-xs font-mono focus:outline-none focus:ring-2 focus:ring-neutral-900 dark:focus:ring-stone-100 leading-relaxed"
            />

            <div className="flex flex-wrap items-center justify-between gap-4 mt-4 pt-4 border-t border-border">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="allowPartialCheck"
                  checked={allowPartial}
                  onChange={(e) => setAllowPartial(e.target.checked)}
                  className="rounded border-border text-neutral-900 focus:ring-neutral-900 dark:focus:ring-stone-100"
                />
                <label htmlFor="allowPartialCheck" className="text-xs font-medium cursor-pointer">
                  Import data valid saja (lewati baris yang error)
                </label>
              </div>

              <div className="flex gap-2">
                <Button
                  onClick={handlePreviewValidation}
                  disabled={!rawText.trim() || isValidating}
                  data-testid="preview-btn"
                >
                  {isValidating ? "Memvalidasi..." : "Preview & Validasi Baris"}
                </Button>
              </div>
            </div>
          </div>
        </div>

        {/* Right Info Guide Panel */}
        <div className="space-y-4">
          <div className="p-5 rounded-lg border border-border bg-card space-y-4">
            <div className="flex items-center gap-2">
              <ShieldCheck size={18} className="text-emerald-600 dark:text-emerald-400" />
              <h3 className="font-display font-bold text-sm tracking-tight">Panduan Import Aman</h3>
            </div>
            <p className="text-xs text-muted-foreground leading-relaxed">
              {currentModObj.desc}. Sistem memeriksa integritas SKU, saldo, tipe numerik, dan duplikasi database sebelum menyimpan perubahan.
            </p>

            <div className="space-y-2 pt-2 border-t border-border text-xs">
              <div className="font-semibold text-foreground flex items-center gap-1.5">
                <FileSpreadsheet size={14} className="text-muted-foreground" /> Format Yang Didukung
              </div>
              <ul className="list-disc list-inside text-muted-foreground space-y-1 pl-1">
                <li>CSV (Pemisah Koma <code className="bg-stone-100 dark:bg-stone-900 px-1 rounded">,</code> atau Titik Koma <code className="bg-stone-100 dark:bg-stone-900 px-1 rounded">;</code>)</li>
                <li>TSV / Salinan langsung dari Microsoft Excel atau Google Sheets</li>
                <li>Pemisah desimal titik <code className="bg-stone-100 dark:bg-stone-900 px-1 rounded">.</code> atau angka ribuan</li>
              </ul>
            </div>

            <div className="space-y-2 pt-2 border-t border-border text-xs">
              <div className="font-semibold text-foreground flex items-center gap-1.5">
                <HelpCircle size={14} className="text-muted-foreground" /> Garansi Rollback Transaksional
              </div>
              <p className="text-muted-foreground leading-relaxed">
                Secara default (Mode Ketat), jika terdapat 1 baris gagal, seluruh transaksi import akan di-rollback sehingga database tetap bersih dan konsisten.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Import Summary Result Banner */}
      {importSummary && (
        <div className="p-6 rounded-lg border border-emerald-300 dark:border-emerald-800/50 bg-emerald-50 dark:bg-emerald-950/20 space-y-4" data-testid="import-success-summary">
          <div className="flex items-center gap-3">
            <CheckCircle2 size={24} className="text-emerald-600 dark:text-emerald-400" />
            <div>
              <h4 className="font-display font-bold text-lg text-emerald-900 dark:text-emerald-200 tracking-tight">
                Import Berhasil Dieksekusi
              </h4>
              <p className="text-xs text-emerald-700 dark:text-emerald-400">
                Data telah tersimpan aman ke database dan pergerakan stok/jurnal telah dicatat.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4 pt-2">
            <div className="p-3 bg-white dark:bg-stone-900 rounded border border-emerald-200 dark:border-emerald-900/40">
              <div className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground">Data Dibuat</div>
              <div className="text-2xl font-bold text-emerald-700 dark:text-emerald-400">{importSummary.created || 0}</div>
            </div>
            <div className="p-3 bg-white dark:bg-stone-900 rounded border border-emerald-200 dark:border-emerald-900/40">
              <div className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground">Data Diperbarui</div>
              <div className="text-2xl font-bold text-neutral-800 dark:text-stone-200">{importSummary.updated || 0}</div>
            </div>
            <div className="p-3 bg-white dark:bg-stone-900 rounded border border-emerald-200 dark:border-emerald-900/40">
              <div className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground">Dilewati (Error)</div>
              <div className="text-2xl font-bold text-amber-600">{importSummary.skipped?.length || 0}</div>
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-2">
            <Button
              onClick={() => navigate(currentModObj.targetRoute)}
              data-testid="go-to-module-btn"
            >
              Lihat di Modul {currentModObj.label} <ArrowRight size={14} className="inline ml-1" />
            </Button>
          </div>
        </div>
      )}

      {/* Live Validation & Preview Table */}
      {validationResult && (
        <div className="space-y-4" data-testid="validation-preview-section">
          <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-lg border border-border bg-card">
            <div className="flex items-center gap-4">
              <div>
                <span className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground">Total Baris</span>
                <div className="font-bold text-xl">{validationResult.total}</div>
              </div>
              <div className="h-8 w-px bg-border" />
              <div>
                <span className="text-[10px] uppercase font-bold tracking-wider text-emerald-700 dark:text-emerald-400">Siap Import</span>
                <div className="font-bold text-xl text-emerald-600 dark:text-emerald-400">{validationResult.valid_count}</div>
              </div>
              <div className="h-8 w-px bg-border" />
              <div>
                <span className="text-[10px] uppercase font-bold tracking-wider text-rose-700 dark:text-rose-400">Error / Gagal</span>
                <div className="font-bold text-xl text-rose-600 dark:text-rose-400">{validationResult.invalid_count}</div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <Button
                onClick={handleExecuteImport}
                disabled={isImporting || (!allowPartial && !validationResult.is_all_valid)}
                data-testid="execute-import-btn"
                className={validationResult.is_all_valid ? "bg-emerald-600 hover:bg-emerald-700 text-white" : ""}
              >
                {isImporting ? (
                  "Menyimpan ke Database..."
                ) : (
                  <>
                    <CheckCircle2 size={14} className="inline mr-1" />
                    Eksekusi Import ({allowPartial ? validationResult.valid_count : validationResult.total} Data)
                  </>
                )}
              </Button>
            </div>
          </div>

          <DataTable
            testid="import-validation-table"
            rows={validationResult.rows}
            columns={[
              {
                header: "Baris",
                cell: (r) => <span className="font-mono text-xs font-semibold">#{r.row_index}</span>,
              },
              {
                header: "Status Validasi",
                cell: (r) => (
                  <div className="space-y-1">
                    {r.is_valid ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-900">
                        <CheckCircle2 size={12} /> Valid
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-100 text-rose-800 dark:bg-rose-950/50 dark:text-rose-400 border border-rose-200 dark:border-rose-900">
                        <XCircle size={12} /> Error
                      </span>
                    )}
                    {r.errors && r.errors.length > 0 && (
                      <div className="text-[11px] text-rose-600 dark:text-rose-400 space-y-0.5">
                        {r.errors.map((err, i) => (
                          <div key={i} className="flex items-center gap-1">
                            <span className="w-1 h-1 rounded-full bg-rose-500" />
                            {err}
                          </div>
                        ))}
                      </div>
                    )}
                    {r.warnings && r.warnings.length > 0 && (
                      <div className="text-[11px] text-amber-600 dark:text-amber-400 space-y-0.5">
                        {r.warnings.map((warn, i) => (
                          <div key={i} className="flex items-center gap-1">
                            <AlertTriangle size={10} />
                            {warn}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ),
              },
              {
                header: "Identifikasi / Nama",
                cell: (r) => {
                  const p = r.parsed || {};
                  return (
                    <div>
                      <div className="font-medium text-xs">
                        {p.name || p.order_number || p.account_name || p.customer_name || "-"}
                      </div>
                      <div className="text-[11px] font-mono text-muted-foreground">
                        {p.sku || p.variant_sku || p.account_code || p.phone || ""}
                      </div>
                    </div>
                  );
                },
              },
              {
                header: "Detail Nilai / Angka",
                cell: (r) => {
                  const p = r.parsed || {};
                  if (selectedModule === "sales_orders") {
                    return (
                      <div className="text-xs space-y-0.5">
                        <div>Qty: <span className="font-semibold">{p.quantity}</span> pcs</div>
                        <div>Harga: <span className="font-semibold">{fmtIDR(p.selling_price)}</span></div>
                        {p.marketplace_fee > 0 && <div className="text-muted-foreground text-[10px]">Fee: {fmtIDR(p.marketplace_fee)}</div>}
                      </div>
                    );
                  }
                  if (selectedModule === "products" || selectedModule === "materials") {
                    return (
                      <div className="text-xs space-y-0.5">
                        <div>Stok: <span className="font-semibold">{p.stock}</span> {p.unit || "pcs"}</div>
                        <div>Harga: <span className="font-semibold">{fmtIDR(p.selling_price || p.cost)}</span></div>
                        {p.cost > 0 && <div className="text-muted-foreground text-[10px]">HPP: {fmtIDR(p.cost)}</div>}
                      </div>
                    );
                  }
                  if (selectedModule === "opening_balance") {
                    return (
                      <div className="text-xs space-y-0.5 font-mono">
                        {p.debit > 0 && <span className="text-emerald-600 font-semibold">Debit: {fmtIDR(p.debit)}</span>}
                        {p.credit > 0 && <span className="text-rose-600 font-semibold">Credit: {fmtIDR(p.credit)}</span>}
                      </div>
                    );
                  }
                  return <span className="text-xs text-muted-foreground">{p.email || p.address || p.customer_type || "-"}</span>;
                },
              },
              {
                header: "Metadata / Kategori",
                cell: (r) => {
                  const p = r.parsed || {};
                  return (
                    <div className="text-xs text-muted-foreground">
                      <div>{p.category || p.sales_channel || p.customer_type || "-"}</div>
                      {(p.color || p.size) && (
                        <div className="text-[10px]">Varian: {p.color} / {p.size}</div>
                      )}
                    </div>
                  );
                },
              },
            ]}
          />
        </div>
      )}
    </div>
  );
}
