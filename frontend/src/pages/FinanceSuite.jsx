import { useEffect, useState, useMemo } from "react";
import { PageHeader, DataTable, Modal, Field, Input, Select, Button, StatusPill, useCRUD } from "./_shared";
import { api, fmtIDR, fmtDate, formatErr } from "@/lib/api";
import { toast } from "sonner";
import { Download, Printer, CheckCircle2, AlertCircle, FileText, BookOpen, RefreshCw, Plus } from "lucide-react";

export default function FinanceSuite() {
  const [tab, setTab] = useState("coa");
  const tabs = [
    ["coa", "Bagan Akun (COA)"],
    ["opening-balance", "Saldo Awal"],
    ["ledger", "Buku Besar & Jurnal"],
    ["reports", "Laporan Akuntansi"],
    ["invoices", "Faktur & Tagihan"],
    ["ap-ar", "Hutang & Piutang"],
    ["bank", "Rekonsiliasi Bank"],
    ["tax", "Pajak"],
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Finance Suite" subtitle="Chart of Accounts, General Ledger & Financial Statements" />
      <div className="flex gap-2 flex-wrap border-b border-border pb-3">
        {tabs.map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all ${
              tab === key
                ? "bg-neutral-900 text-white dark:bg-stone-100 dark:text-stone-900 shadow-sm"
                : "bg-stone-100 hover:bg-stone-200 dark:bg-stone-900 dark:hover:bg-stone-800 text-muted-foreground"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "coa" && <ChartOfAccounts />}
      {tab === "opening-balance" && <OpeningBalance />}
      {tab === "ledger" && <Ledger />}
      {tab === "reports" && <FinancialReports />}
      {tab === "invoices" && <Invoices />}
      {tab === "ap-ar" && <ApAr />}
      {tab === "bank" && <BankReconciliation />}
      {tab === "tax" && <Tax />}
    </div>
  );
}

// ==========================================
// 1. CHART OF ACCOUNTS (COA)
// ==========================================
function ChartOfAccounts() {
  const { rows: accounts, save, remove, reload } = useCRUD("accounts");
  const [filterType, setFilterType] = useState("all");
  const [modal, setModal] = useState(null);

  const typeLabels = {
    all: "Semua Kategori",
    asset: "1 - Aset",
    liability: "2 - Kewajiban",
    equity: "3 - Ekuitas",
    revenue: "4 - Pendapatan",
    cogs: "5 - HPP",
    expense: "6 - Beban Operasional",
  };

  const typeBadges = {
    asset: "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-300",
    liability: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950 dark:text-amber-300",
    equity: "bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950 dark:text-purple-300",
    revenue: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950 dark:text-emerald-300",
    cogs: "bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-950 dark:text-orange-300",
    expense: "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950 dark:text-rose-300",
  };

  const filteredAccounts = useMemo(() => {
    if (filterType === "all") return accounts;
    return accounts.filter((a) => a.account_type === filterType);
  }, [accounts, filterType]);

  const handleOpenAdd = () => {
    setModal({
      code: "",
      name: "",
      account_type: "asset",
      subtype: "Kas & Bank",
      normal_balance: "debit",
      kind: "cash",
      balance: 0,
      is_default: false,
    });
  };

  const handleSave = async () => {
    try {
      if (!modal.code || !modal.name) {
        toast.error("Kode akun dan nama wajib diisi");
        return;
      }
      await save(modal, modal.id);
      toast.success("Akun berhasil disimpan");
      setModal(null);
      reload();
    } catch (e) {
      toast.error(formatErr(e.response?.data?.detail));
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-1.5 flex-wrap">
          {Object.entries(typeLabels).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setFilterType(key)}
              className={`px-3 py-1.5 rounded-md text-xs font-semibold border transition-colors ${
                filterType === key
                  ? "bg-neutral-900 text-white border-neutral-900 dark:bg-stone-100 dark:text-stone-900"
                  : "bg-card border-border hover:bg-stone-50 dark:hover:bg-stone-900 text-muted-foreground"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <Button onClick={handleOpenAdd}>+ Tambah Akun COA</Button>
      </div>

      <DataTable
        rows={filteredAccounts}
        columns={[
          { header: "Kode", cell: (r) => <span className="font-mono font-bold text-xs">{r.code || "-"}</span> },
          {
            header: "Nama Akun",
            cell: (r) => (
              <div>
                <span className="font-semibold text-foreground">{r.name}</span>
                {r.is_default && <span className="ml-2 text-[10px] bg-neutral-200 dark:bg-neutral-800 px-1.5 py-0.5 rounded font-bold uppercase">Utama</span>}
                {r.is_system && <span className="ml-1.5 text-[10px] text-muted-foreground italic">(Sistem)</span>}
              </div>
            ),
          },
          {
            header: "Kategori",
            cell: (r) => (
              <span className={`px-2 py-0.5 text-[10px] uppercase font-bold rounded border ${typeBadges[r.account_type] || "bg-stone-100"}`}>
                {r.account_type || "asset"}
              </span>
            ),
          },
          { header: "Subtipe", cell: (r) => <span className="text-xs text-muted-foreground">{r.subtype || "-"}</span> },
          { header: "Saldo Normal", cell: (r) => <span className="text-xs uppercase font-semibold">{r.normal_balance || "debit"}</span> },
          { header: "Saldo Berjalan", cell: (r) => <b className="font-mono">{fmtIDR(r.balance || 0)}</b> },
          {
            header: "Aksi",
            cell: (r) => (
              <div className="flex gap-2">
                <button className="text-blue-600 hover:underline text-xs" onClick={() => setModal({ ...r })}>Edit</button>
                {!r.is_system && (
                  <button className="text-rose-600 hover:underline text-xs" onClick={() => remove(r.id)}>Hapus</button>
                )}
              </div>
            ),
          },
        ]}
      />

      {modal && (
        <Modal open onClose={() => setModal(null)} title={modal.id ? `Edit Akun: ${modal.name}` : "Tambah Akun Baru"}>
          <div className="space-y-4">
            <div className="grid sm:grid-cols-2 gap-3">
              <Field label="Kode Akun (cth: 1-10001)">
                <Input value={modal.code} onChange={(e) => setModal({ ...modal, code: e.target.value })} placeholder="1-10001" />
              </Field>
              <Field label="Nama Akun">
                <Input value={modal.name} onChange={(e) => setModal({ ...modal, name: e.target.value })} placeholder="Nama akun" />
              </Field>
            </div>

            <div className="grid sm:grid-cols-3 gap-3">
              <Field label="Kategori Utama">
                <Select
                  value={modal.account_type}
                  onChange={(e) => {
                    const at = e.target.value;
                    const defaultNorm = ["liability", "equity", "revenue"].includes(at) ? "credit" : "debit";
                    setModal({ ...modal, account_type: at, normal_balance: defaultNorm });
                  }}
                >
                  <option value="asset">1 - Aset</option>
                  <option value="liability">2 - Kewajiban</option>
                  <option value="equity">3 - Ekuitas</option>
                  <option value="revenue">4 - Pendapatan</option>
                  <option value="cogs">5 - HPP</option>
                  <option value="expense">6 - Beban Operasional</option>
                </Select>
              </Field>
              <Field label="Subtipe Akun">
                <Input value={modal.subtype} onChange={(e) => setModal({ ...modal, subtype: e.target.value })} placeholder="cth: Kas & Bank" />
              </Field>
              <Field label="Saldo Normal">
                <Select value={modal.normal_balance} onChange={(e) => setModal({ ...modal, normal_balance: e.target.value })}>
                  <option value="debit">Debit</option>
                  <option value="credit">Kredit</option>
                </Select>
              </Field>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-border">
              <Button variant="outline" onClick={() => setModal(null)}>Batal</Button>
              <Button onClick={handleSave}>Simpan Akun</Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ==========================================
// 2. OPENING BALANCE (SALDO AWAL)
// ==========================================
function OpeningBalance() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [asOfDate, setAsOfDate] = useState("2026-01-01");
  const [lines, setLines] = useState([]);
  const [autoBalance, setAutoBalance] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get("/finance/opening-balance");
      setData(res.data);
      setAsOfDate(res.data.as_of_date || "2026-01-01");
      setLines(
        (res.data.accounts || []).map((a) => ({
          account_id: a.id,
          code: a.code,
          name: a.name,
          account_type: a.account_type,
          normal_balance: a.normal_balance,
          debit: a.opening_debit || 0,
          credit: a.opening_credit || 0,
        }))
      );
    } catch (e) {
      toast.error("Gagal memuat saldo awal");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const { totalDebit, totalCredit, diff, isBalanced } = useMemo(() => {
    const td = lines.reduce((sum, l) => sum + (Number(l.debit) || 0), 0);
    const tc = lines.reduce((sum, l) => sum + (Number(l.credit) || 0), 0);
    const d = Math.round((td - tc) * 100) / 100;
    return { totalDebit: td, totalCredit: tc, diff: d, isBalanced: Math.abs(d) < 0.01 };
  }, [lines]);

  const handleLineChange = (index, field, value) => {
    const updated = [...lines];
    updated[index][field] = Number(value) || 0;
    setLines(updated);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.post("/finance/opening-balance", {
        as_of_date: asOfDate,
        auto_balance: autoBalance,
        lines: lines.map((l) => ({
          account_id: l.account_id,
          debit: Number(l.debit || 0),
          credit: Number(l.credit || 0),
        })),
      });
      toast.success("Saldo awal berhasil disimpan & diselaraskan!");
      load();
    } catch (e) {
      toast.error(formatErr(e.response?.data?.detail || "Gagal menyimpan saldo awal"));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="p-8 text-center text-muted-foreground">Memuat struktur saldo awal...</div>;

  return (
    <div className="space-y-6">
      <div className="p-5 rounded-xl border border-border bg-card flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold">Input Saldo Awal Neraca</h2>
          <p className="text-xs text-muted-foreground">
            Masukkan posisi saldo akun sebelum tanggal cut-off mulai operasional sistem ERP.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Field label="Tanggal Cut-Off">
            <Input type="date" value={asOfDate} onChange={(e) => setAsOfDate(e.target.value)} className="w-40" />
          </Field>
          <Button onClick={handleSave} disabled={saving} className="mt-4">
            {saving ? "Menyimpan..." : "Simpan Saldo Awal"}
          </Button>
        </div>
      </div>

      <div className="grid sm:grid-cols-4 gap-4">
        <div className="p-4 rounded-lg border border-border bg-card">
          <div className="text-[10px] uppercase font-bold text-muted-foreground">Total Debit</div>
          <div className="text-xl font-bold font-mono text-emerald-600 dark:text-emerald-400">{fmtIDR(totalDebit)}</div>
        </div>
        <div className="p-4 rounded-lg border border-border bg-card">
          <div className="text-[10px] uppercase font-bold text-muted-foreground">Total Kredit</div>
          <div className="text-xl font-bold font-mono text-blue-600 dark:text-blue-400">{fmtIDR(totalCredit)}</div>
        </div>
        <div className="p-4 rounded-lg border border-border bg-card">
          <div className="text-[10px] uppercase font-bold text-muted-foreground">Selisih (Debit - Kredit)</div>
          <div className={`text-xl font-bold font-mono ${diff === 0 ? "text-muted-foreground" : "text-amber-600 dark:text-amber-400"}`}>
            {fmtIDR(Math.abs(diff))}
          </div>
        </div>
        <div className={`p-4 rounded-lg border flex items-center gap-3 ${
          isBalanced ? "bg-emerald-50 border-emerald-200 text-emerald-800 dark:bg-emerald-950/40 dark:border-emerald-900 dark:text-emerald-300"
                     : "bg-amber-50 border-amber-200 text-amber-800 dark:bg-amber-950/40 dark:border-amber-900 dark:text-amber-300"
        }`}>
          {isBalanced ? <CheckCircle2 size={24} className="text-emerald-600" /> : <AlertCircle size={24} className="text-amber-600" />}
          <div>
            <div className="text-xs font-bold uppercase tracking-wider">{isBalanced ? "Neraca Seimbang" : "Belum Seimbang"}</div>
            <div className="text-[11px] opacity-80">
              {isBalanced ? "Total Debit & Kredit sama" : "Akan otomatis diseimbangkan ke Ekuitas Saldo Awal"}
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Daftar Akun Saldo Awal</span>
          <label className="flex items-center gap-2 text-xs font-semibold cursor-pointer">
            <input type="checkbox" checked={autoBalance} onChange={(e) => setAutoBalance(e.target.checked)} className="rounded" />
            Otomatis seimbangkan selisih ke <i>Ekuitas Saldo Awal (3-10001)</i>
          </label>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-stone-100 dark:bg-stone-900 text-[10px] uppercase tracking-widest text-muted-foreground">
              <tr>
                <th className="px-4 py-3 text-left">Kode</th>
                <th className="px-4 py-3 text-left">Nama Akun</th>
                <th className="px-4 py-3 text-left">Kategori</th>
                <th className="px-4 py-3 text-left">Saldo Normal</th>
                <th className="px-4 py-3 text-right w-44">Debit (Rp)</th>
                <th className="px-4 py-3 text-right w-44">Kredit (Rp)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {lines.map((l, i) => (
                <tr key={l.account_id} className="hover:bg-stone-50 dark:hover:bg-stone-900/50">
                  <td className="px-4 py-2 font-mono text-xs font-bold">{l.code}</td>
                  <td className="px-4 py-2 font-medium">{l.name}</td>
                  <td className="px-4 py-2 text-xs uppercase text-muted-foreground">{l.account_type}</td>
                  <td className="px-4 py-2 text-xs uppercase font-semibold text-muted-foreground">{l.normal_balance}</td>
                  <td className="px-4 py-2">
                    <Input
                      type="number"
                      value={l.debit}
                      onChange={(e) => handleLineChange(i, "debit", e.target.value)}
                      className="text-right font-mono text-xs py-1"
                      placeholder="0"
                    />
                  </td>
                  <td className="px-4 py-2">
                    <Input
                      type="number"
                      value={l.credit}
                      onChange={(e) => handleLineChange(i, "credit", e.target.value)}
                      className="text-right font-mono text-xs py-1"
                      placeholder="0"
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ==========================================
// 3. BUKU BESAR & JURNAL (GENERAL LEDGER)
// ==========================================
function Ledger() {
  const { rows: accounts } = useCRUD("accounts");
  const [mode, setMode] = useState("journal"); // journal | ledger
  const [rows, setRows] = useState([]);
  const [modal, setModal] = useState(null);

  // General Ledger state
  const [selectedAccId, setSelectedAccId] = useState("");
  const [glData, setGlData] = useState(null);
  const [glStart, setGlStart] = useState("");
  const [glEnd, setGlEnd] = useState("");
  const [glLoading, setGlLoading] = useState(false);

  const reloadJournal = () => api.get("/finance/journal_entries").then((r) => setRows(r.data));

  useEffect(() => {
    reloadJournal();
  }, []);

  useEffect(() => {
    if (accounts.length > 0 && !selectedAccId) {
      setSelectedAccId(accounts[0].id);
    }
  }, [accounts, selectedAccId]);

  const loadGeneralLedger = async () => {
    if (!selectedAccId) return;
    setGlLoading(true);
    try {
      const res = await api.get(`/reports/general_ledger?account_id=${selectedAccId}&start=${glStart}&end=${glEnd}`);
      setGlData(res.data);
    } catch (e) {
      toast.error("Gagal memuat buku besar akun");
    } finally {
      setGlLoading(false);
    }
  };

  useEffect(() => {
    if (mode === "ledger" && selectedAccId) {
      loadGeneralLedger();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, selectedAccId, glStart, glEnd]);

  const saveJournal = async () => {
    try {
      await api.post("/finance/journal_entries", {
        ...modal,
        lines: modal.lines.map((x) => ({ ...x, debit: Number(x.debit || 0), credit: Number(x.credit || 0) })),
      });
      toast.success("Jurnal umum tersimpan");
      setModal(null);
      reloadJournal();
    } catch (e) {
      toast.error(formatErr(e.response?.data?.detail));
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3 border-b border-border pb-3">
        <div className="flex gap-2">
          <Button variant={mode === "journal" ? "primary" : "outline"} onClick={() => setMode("journal")}>
            Jurnal Umum
          </Button>
          <Button variant={mode === "ledger" ? "primary" : "outline"} onClick={() => setMode("ledger")}>
            Buku Besar per Akun
          </Button>
        </div>
        {mode === "journal" && (
          <Button
            onClick={() =>
              setModal({
                description: "",
                reference: "",
                date: new Date().toISOString().slice(0, 10),
                lines: [
                  { account_id: "", debit: 0, credit: 0 },
                  { account_id: "", debit: 0, credit: 0 },
                ],
              })
            }
          >
            + Jurnal Umum Baru
          </Button>
        )}
      </div>

      {mode === "journal" && (
        <DataTable
          rows={rows}
          columns={[
            { header: "Tanggal", cell: (r) => fmtDate(r.date) },
            { header: "Referensi", cell: (r) => <span className="font-mono text-xs">{r.reference || "-"}</span> },
            { header: "Deskripsi", cell: (r) => r.description },
            { header: "Tipe Sumber", cell: (r) => <span className="text-xs uppercase bg-stone-100 dark:bg-stone-800 px-2 py-0.5 rounded">{r.source_type || "manual"}</span> },
            { header: "Total Jurnal", cell: (r) => <b>{fmtIDR(r.total)}</b> },
          ]}
        />
      )}

      {mode === "ledger" && (
        <div className="space-y-4">
          <div className="p-4 rounded-lg border border-border bg-card flex flex-wrap items-end gap-4">
            <Field label="Pilih Akun Buku Besar">
              <Select value={selectedAccId} onChange={(e) => setSelectedAccId(e.target.value)} className="min-w-[260px]">
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.code ? `[${a.code}] ` : ""}{a.name}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Dari Tanggal">
              <Input type="date" value={glStart} onChange={(e) => setGlStart(e.target.value)} />
            </Field>
            <Field label="Sampai Tanggal">
              <Input type="date" value={glEnd} onChange={(e) => setGlEnd(e.target.value)} />
            </Field>
            <div className="flex gap-2">
              <Button variant="outline" onClick={loadGeneralLedger}><RefreshCw size={14} className="mr-1.5" /> Refresh</Button>
              <Button variant="outline" onClick={() => window.open(`/api/reports/export/general_ledger?account_id=${selectedAccId}&start=${glStart}&end=${glEnd}`, "_blank")}><Download size={14} className="mr-1.5" /> CSV</Button>
              <Button variant="outline" onClick={() => window.open(`/api/reports/pdf/general_ledger?account_id=${selectedAccId}&start=${glStart}&end=${glEnd}`, "_blank")}><FileText size={14} className="mr-1.5" /> PDF</Button>
            </div>
          </div>

          {glData && (
            <div className="space-y-4">
              <div className="grid sm:grid-cols-3 gap-4">
                <Summary title="Total Mutasi Debit" value={glData.total_debit} />
                <Summary title="Total Mutasi Kredit" value={glData.total_credit} />
                <Summary title="Saldo Akhir Buku Besar" value={glData.ending_balance} />
              </div>

              <DataTable
                rows={glData.transactions || []}
                columns={[
                  { header: "Tanggal", cell: (r) => fmtDate(r.date) },
                  { header: "Referensi", cell: (r) => <span className="font-mono text-xs">{r.reference}</span> },
                  { header: "Deskripsi", cell: (r) => r.description },
                  { header: "Debit", cell: (r) => <span className="font-mono">{r.debit > 0 ? fmtIDR(r.debit) : "-"}</span> },
                  { header: "Kredit", cell: (r) => <span className="font-mono">{r.credit > 0 ? fmtIDR(r.credit) : "-"}</span> },
                  { header: "Saldo Berjalan", cell: (r) => <b className="font-mono">{fmtIDR(r.running_balance)}</b> },
                ]}
                empty="Belum ada mutasi jurnal untuk akun ini pada periode yang dipilih"
              />
            </div>
          )}
        </div>
      )}

      {modal && (
        <Modal open onClose={() => setModal(null)} title="Buat Jurnal Umum">
          <div className="space-y-4">
            <div className="grid sm:grid-cols-3 gap-3">
              <Field label="Tanggal Jurnal">
                <Input type="date" value={modal.date} onChange={(e) => setModal({ ...modal, date: e.target.value })} />
              </Field>
              <Field label="Nomor Referensi">
                <Input value={modal.reference} onChange={(e) => setModal({ ...modal, reference: e.target.value })} placeholder="cth: JV-001" />
              </Field>
              <Field label="Deskripsi">
                <Input value={modal.description} onChange={(e) => setModal({ ...modal, description: e.target.value })} placeholder="Keterangan transaksi" />
              </Field>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-bold uppercase text-muted-foreground">Baris Akun (Debit / Kredit)</label>
              {modal.lines.map((line, i) => (
                <div className="grid grid-cols-[1fr_130px_130px_36px] gap-2 items-center" key={i}>
                  <Select
                    value={line.account_id}
                    onChange={(e) => {
                      const lines = [...modal.lines];
                      lines[i] = { ...line, account_id: e.target.value };
                      setModal({ ...modal, lines });
                    }}
                  >
                    <option value="">-- Pilih Akun --</option>
                    {accounts.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.code ? `[${a.code}] ` : ""}{a.name}
                      </option>
                    ))}
                  </Select>
                  <Input
                    type="number"
                    placeholder="Debit"
                    value={line.debit}
                    onChange={(e) => {
                      const lines = [...modal.lines];
                      lines[i] = { ...line, debit: e.target.value };
                      setModal({ ...modal, lines });
                    }}
                  />
                  <Input
                    type="number"
                    placeholder="Kredit"
                    value={line.credit}
                    onChange={(e) => {
                      const lines = [...modal.lines];
                      lines[i] = { ...line, credit: e.target.value };
                      setModal({ ...modal, lines });
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => {
                      if (modal.lines.length <= 2) {
                        toast.error("Minimal harus 2 baris akun");
                        return;
                      }
                      setModal({ ...modal, lines: modal.lines.filter((_, idx) => idx !== i) });
                    }}
                    className="text-rose-600 hover:text-rose-700 font-bold p-1 text-center"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-border">
              <Button variant="outline" onClick={() => setModal({ ...modal, lines: [...modal.lines, { account_id: "", debit: 0, credit: 0 }] })}>
                + Tambah Baris
              </Button>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setModal(null)}>Batal</Button>
                <Button onClick={saveJournal}>Simpan Jurnal</Button>
              </div>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ==========================================
// 4. FINANCIAL STATEMENTS (LAPORAN AKUNTANSI)
// ==========================================
function FinancialReports() {
  const [reportType, setReportType] = useState("balance_sheet"); // balance_sheet | profit_loss | trial_balance
  const [asOfDate, setAsOfDate] = useState(new Date().toISOString().slice(0, 10));
  const [startDate, setStartDate] = useState(new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().slice(0, 10));
  const [endDate, setEndDate] = useState(new Date().toISOString().slice(0, 10));
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadReport = async () => {
    setLoading(true);
    try {
      if (reportType === "balance_sheet") {
        const res = await api.get(`/reports/balance_sheet?as_of_date=${asOfDate}`);
        setData(res.data);
      } else if (reportType === "trial_balance") {
        const res = await api.get(`/reports/trial_balance?as_of_date=${asOfDate}`);
        setData(res.data);
      } else if (reportType === "profit_loss") {
        const res = await api.get(`/reports/profit_loss?start=${startDate}&end=${endDate}`);
        setData(res.data);
      }
    } catch (e) {
      toast.error("Gagal memuat laporan keuangan");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReport();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportType, asOfDate, startDate, endDate]);

  const handleExportCSV = () => {
    const baseUrl = api.defaults?.baseURL || "/api";
    if (reportType === "balance_sheet") {
      window.open(`${baseUrl}/reports/export/balance_sheet?as_of_date=${asOfDate}`, "_blank");
    } else if (reportType === "trial_balance") {
      window.open(`${baseUrl}/reports/export/trial_balance?as_of_date=${asOfDate}`, "_blank");
    } else {
      window.open(`${baseUrl}/reports/export/profit_loss?start=${startDate}&end=${endDate}`, "_blank");
    }
  };

  const handleExportPDF = () => {
    const baseUrl = api.defaults?.baseURL || "/api";
    if (reportType === "balance_sheet") {
      window.open(`${baseUrl}/reports/pdf/balance_sheet?as_of_date=${asOfDate}`, "_blank");
    } else if (reportType === "trial_balance") {
      window.open(`${baseUrl}/reports/pdf/trial_balance?as_of_date=${asOfDate}`, "_blank");
    } else {
      window.open(`${baseUrl}/reports/pdf/profit_loss?start=${startDate}&end=${endDate}`, "_blank");
    }
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="space-y-6">
      <div className="p-4 rounded-xl border border-border bg-card flex flex-wrap items-end justify-between gap-4">
        <div className="flex gap-2 flex-wrap">
          <Button variant={reportType === "balance_sheet" ? "primary" : "outline"} onClick={() => setReportType("balance_sheet")}>
            Neraca (Balance Sheet)
          </Button>
          <Button variant={reportType === "profit_loss" ? "primary" : "outline"} onClick={() => setReportType("profit_loss")}>
            Laba Rugi (Income Statement)
          </Button>
          <Button variant={reportType === "trial_balance" ? "primary" : "outline"} onClick={() => setReportType("trial_balance")}>
            Neraca Saldo (Trial Balance)
          </Button>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {reportType === "profit_loss" ? (
            <>
              <Field label="Dari"><Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} /></Field>
              <Field label="Sampai"><Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} /></Field>
            </>
          ) : (
            <Field label="Per Tanggal"><Input type="date" value={asOfDate} onChange={(e) => setAsOfDate(e.target.value)} /></Field>
          )}
          <Button variant="outline" onClick={handleExportCSV} className="mt-4"><Download size={14} className="mr-1.5" /> CSV</Button>
          <Button variant="outline" onClick={handleExportPDF} className="mt-4"><FileText size={14} className="mr-1.5" /> PDF Resmi</Button>
          <Button variant="outline" onClick={handlePrint} className="mt-4"><Printer size={14} className="mr-1.5" /> Cetak</Button>
        </div>
      </div>

      {loading && <div className="p-8 text-center text-muted-foreground">Menghitung laporan akuntansi...</div>}

      {/* 1. NERACA (BALANCE SHEET) VIEW */}
      {!loading && reportType === "balance_sheet" && data && (
        <div className="space-y-6">
          <div className="grid md:grid-cols-2 gap-6">
            {/* SISI KIRI: ASET */}
            <div className="p-6 rounded-xl border border-border bg-card space-y-5">
              <div className="border-b border-border pb-2 flex items-center justify-between">
                <h3 className="text-base font-black uppercase tracking-wider">1. Aset (Assets)</h3>
                <span className="font-mono font-bold text-emerald-600 dark:text-emerald-400">{fmtIDR(data.total_assets)}</span>
              </div>

              <div>
                <div className="text-xs font-bold uppercase text-muted-foreground mb-2">Aset Lancar</div>
                <div className="space-y-1.5 text-sm">
                  {data.current_assets.map((a) => (
                    <div key={a.id || a.code} className="flex justify-between py-1 border-b border-border/50">
                      <span className="text-muted-foreground"><span className="font-mono text-xs text-foreground font-semibold mr-1.5">{a.code}</span>{a.name}</span>
                      <span className="font-mono font-medium">{fmtIDR(a.amount || 0)}</span>
                    </div>
                  ))}
                  <div className="flex justify-between pt-2 font-bold text-xs uppercase">
                    <span>Total Aset Lancar</span>
                    <span className="font-mono">{fmtIDR(data.total_current_assets)}</span>
                  </div>
                </div>
              </div>

              {data.fixed_assets.length > 0 && (
                <div>
                  <div className="text-xs font-bold uppercase text-muted-foreground mb-2">Aset Tetap & Peralatan</div>
                  <div className="space-y-1.5 text-sm">
                    {data.fixed_assets.map((a) => (
                      <div key={a.id || a.code} className="flex justify-between py-1 border-b border-border/50">
                        <span className="text-muted-foreground"><span className="font-mono text-xs text-foreground font-semibold mr-1.5">{a.code}</span>{a.name}</span>
                        <span className="font-mono font-medium">{fmtIDR(a.amount || 0)}</span>
                      </div>
                    ))}
                    <div className="flex justify-between pt-2 font-bold text-xs uppercase">
                      <span>Total Aset Tetap</span>
                      <span className="font-mono">{fmtIDR(data.total_fixed_assets)}</span>
                    </div>
                  </div>
                </div>
              )}

              <div className="pt-4 border-t-2 border-border flex justify-between items-center text-lg font-black">
                <span>TOTAL ASET</span>
                <span className="font-mono text-emerald-600 dark:text-emerald-400">{fmtIDR(data.total_assets)}</span>
              </div>
            </div>

            {/* SISI KANAN: KEWAJIBAN & EKUITAS */}
            <div className="p-6 rounded-xl border border-border bg-card space-y-5">
              <div className="border-b border-border pb-2 flex items-center justify-between">
                <h3 className="text-base font-black uppercase tracking-wider">2 & 3. Kewajiban & Ekuitas</h3>
                <span className="font-mono font-bold text-blue-600 dark:text-blue-400">{fmtIDR(data.total_liabilities_and_equity)}</span>
              </div>

              <div>
                <div className="text-xs font-bold uppercase text-muted-foreground mb-2">Kewajiban (Liabilities)</div>
                <div className="space-y-1.5 text-sm">
                  {data.current_liabilities.map((a) => (
                    <div key={a.id || a.code} className="flex justify-between py-1 border-b border-border/50">
                      <span className="text-muted-foreground"><span className="font-mono text-xs text-foreground font-semibold mr-1.5">{a.code}</span>{a.name}</span>
                      <span className="font-mono font-medium">{fmtIDR(a.amount || 0)}</span>
                    </div>
                  ))}
                  <div className="flex justify-between pt-2 font-bold text-xs uppercase">
                    <span>Total Kewajiban</span>
                    <span className="font-mono">{fmtIDR(data.total_liabilities)}</span>
                  </div>
                </div>
              </div>

              <div>
                <div className="text-xs font-bold uppercase text-muted-foreground mb-2">Ekuitas (Equity)</div>
                <div className="space-y-1.5 text-sm">
                  {data.equity.map((a) => (
                    <div key={a.id || a.code} className="flex justify-between py-1 border-b border-border/50">
                      <span className="text-muted-foreground"><span className="font-mono text-xs text-foreground font-semibold mr-1.5">{a.code}</span>{a.name}</span>
                      <span className={`font-mono font-medium ${a.amount < 0 ? "text-rose-600" : ""}`}>{fmtIDR(a.amount || 0)}</span>
                    </div>
                  ))}
                  <div className="flex justify-between pt-2 font-bold text-xs uppercase">
                    <span>Total Ekuitas</span>
                    <span className="font-mono">{fmtIDR(data.total_equity)}</span>
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t-2 border-border flex justify-between items-center text-lg font-black">
                <span>TOTAL KEWAJIBAN & EKUITAS</span>
                <span className="font-mono text-blue-600 dark:text-blue-400">{fmtIDR(data.total_liabilities_and_equity)}</span>
              </div>
            </div>
          </div>

          {/* Balance Check Indicator */}
          <div className={`p-4 rounded-xl border flex items-center justify-between ${
            data.is_balanced
              ? "bg-emerald-50 border-emerald-200 text-emerald-900 dark:bg-emerald-950/40 dark:border-emerald-900 dark:text-emerald-300"
              : "bg-amber-50 border-amber-200 text-amber-900 dark:bg-amber-950/40 dark:border-amber-900 dark:text-amber-300"
          }`}>
            <div className="flex items-center gap-3">
              {data.is_balanced ? <CheckCircle2 size={24} className="text-emerald-600" /> : <AlertCircle size={24} className="text-amber-600" />}
              <div>
                <div className="font-bold text-sm">
                  {data.is_balanced ? "Neraca Seimbang (Balanced)" : "Terdapat Selisih Neraca"}
                </div>
                <div className="text-xs opacity-85">
                  Formula: Total Aset ({fmtIDR(data.total_assets)}) = Total Kewajiban & Ekuitas ({fmtIDR(data.total_liabilities_and_equity)})
                </div>
              </div>
            </div>
            {!data.is_balanced && (
              <span className="font-mono font-bold text-sm bg-amber-200 dark:bg-amber-900 px-2.5 py-1 rounded">
                Selisih: {fmtIDR(Math.abs(data.difference))}
              </span>
            )}
          </div>
        </div>
      )}

      {/* 2. LABA RUGI (INCOME STATEMENT) VIEW */}
      {!loading && reportType === "profit_loss" && data && (
        <div className="p-6 rounded-xl border border-border bg-card space-y-6 max-w-3xl mx-auto">
          <div className="text-center border-b border-border pb-4">
            <h2 className="text-xl font-black uppercase tracking-tight">Laporan Laba Rugi</h2>
            <p className="text-xs text-muted-foreground">Periode: {fmtDate(startDate)} s/d {fmtDate(endDate)}</p>
          </div>

          <div className="space-y-4 text-sm">
            <div className="flex justify-between py-2 border-b border-border font-bold">
              <span>Pendapatan Penjualan (Revenue)</span>
              <span className="font-mono text-emerald-600 dark:text-emerald-400">{fmtIDR(data.revenue)}</span>
            </div>
            <div className="flex justify-between py-1 text-muted-foreground">
              <span>Beban Pokok Penjualan (COGS / HPP)</span>
              <span className="font-mono text-rose-600 dark:text-rose-400">({fmtIDR(data.cogs)})</span>
            </div>
            <div className="flex justify-between py-2 border-t border-b border-border font-bold bg-stone-50 dark:bg-stone-900 px-3 rounded">
              <span>Laba Kotor (Gross Profit)</span>
              <span className="font-mono">{fmtIDR(data.gross_profit)}</span>
            </div>

            <div className="pt-2 space-y-2">
              <div className="text-xs font-bold uppercase text-muted-foreground">Beban Operasional:</div>
              <div className="flex justify-between text-muted-foreground pl-4">
                <span>Biaya Admin & Layanan Marketplace</span>
                <span className="font-mono">({fmtIDR(data.marketplace_fees)})</span>
              </div>
              <div className="flex justify-between text-muted-foreground pl-4">
                <span>Biaya Iklan & Promosi (Advertising)</span>
                <span className="font-mono">({fmtIDR(data.advertising)})</span>
              </div>
              <div className="flex justify-between text-muted-foreground pl-4">
                <span>Beban Operasional Umum (Listrik, Sewa, Gaji)</span>
                <span className="font-mono">({fmtIDR(data.operating_expenses)})</span>
              </div>
            </div>

            <div className="flex justify-between py-3 border-t-2 border-border font-black text-lg bg-neutral-900 text-white dark:bg-stone-100 dark:text-stone-900 px-4 rounded-lg">
              <span>LABA BERSIH (NET PROFIT)</span>
              <span className="font-mono">{fmtIDR(data.net_profit)}</span>
            </div>
          </div>
        </div>
      )}

      {/* 3. NERACA SALDO (TRIAL BALANCE) VIEW */}
      {!loading && reportType === "trial_balance" && data && (
        <div className="space-y-4">
          <DataTable
            rows={data.rows || []}
            columns={[
              { header: "Kode", cell: (r) => <span className="font-mono font-bold text-xs">{r.code}</span> },
              { header: "Nama Akun", cell: (r) => <span className="font-semibold">{r.name}</span> },
              { header: "Kategori", cell: (r) => <span className="text-xs uppercase text-muted-foreground">{r.account_type}</span> },
              { header: "Posisi Debit", cell: (r) => <span className="font-mono">{r.debit > 0 ? fmtIDR(r.debit) : "-"}</span> },
              { header: "Posisi Kredit", cell: (r) => <span className="font-mono">{r.credit > 0 ? fmtIDR(r.credit) : "-"}</span> },
            ]}
          />

          <div className="p-4 rounded-xl border border-border bg-card flex justify-between items-center text-sm font-bold font-mono">
            <span>TOTAL NERACA SALDO</span>
            <div className="flex gap-8">
              <span>Debit: <b className="text-emerald-600">{fmtIDR(data.total_debit)}</b></span>
              <span>Kredit: <b className="text-blue-600">{fmtIDR(data.total_credit)}</b></span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ==========================================
// 5. INVOICES & BILLS
// ==========================================
function Invoices() {
  const { rows: invoices, save, remove, reload: reloadInvoices } = useCRUD("invoices");
  const { rows: bills, reload: reloadBills } = useCRUD("bills");
  const { rows: accounts } = useCRUD("accounts");
  const [kind, setKind] = useState("invoice");
  const [form, setForm] = useState(null);
  const [payment, setPayment] = useState(null);

  const collection = kind === "invoice" ? invoices : bills;
  const submit = async () => {
    if (await save({ ...form, amount: Number(form.amount), paid_amount: 0, status: "unpaid" }, form.id)) setForm(null);
  };
  const pay = async () => {
    try {
      await api.post(`/finance/${payment.kind === "invoice" ? "invoices" : "bills"}/${payment.id}/payment`, {
        amount: Number(payment.amount),
        account_id: payment.account_id,
      });
      toast.success("Pembayaran berhasil dicatat");
      setPayment(null);
      reloadInvoices();
      reloadBills();
    } catch (e) {
      toast.error(formatErr(e.response?.data?.detail));
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center mb-3">
        <div className="flex gap-2">
          <Button variant={kind === "invoice" ? "primary" : "outline"} onClick={() => setKind("invoice")}>
            Faktur Penjualan (Sales Invoice)
          </Button>
          <Button variant={kind === "bill" ? "primary" : "outline"} onClick={() => setKind("bill")}>
            Tagihan Pembelian (Vendor Bill)
          </Button>
        </div>
        <Button onClick={() => setForm({ number: "", party_name: "", amount: 0, due_date: "", description: "" })}>
          + {kind === "invoice" ? "Invoice" : "Bill"} Baru
        </Button>
      </div>

      <DataTable
        rows={collection}
        columns={[
          { header: "Nomor", cell: (r) => <span className="font-mono font-bold text-xs">{r.number}</span> },
          { header: "Pihak", cell: (r) => r.party_name },
          { header: "Jatuh Tempo", cell: (r) => fmtDate(r.due_date) },
          { header: "Total Nominal", cell: (r) => <span className="font-mono font-semibold">{fmtIDR(r.amount)}</span> },
          { header: "Terbayar", cell: (r) => <span className="font-mono text-emerald-600">{fmtIDR(r.paid_amount)}</span> },
          { header: "Status", cell: (r) => <StatusPill status={r.status || "unpaid"} /> },
          {
            header: "Aksi",
            cell: (r) => (
              <div className="flex gap-2">
                <button
                  className="text-blue-600 hover:underline text-xs font-semibold"
                  disabled={Number(r.paid_amount || 0) >= Number(r.amount || 0)}
                  onClick={() =>
                    setPayment({
                      id: r.id,
                      kind,
                      amount: Number(r.amount || 0) - Number(r.paid_amount || 0),
                      account_id: accounts.find((a) => a.is_default)?.id || accounts[0]?.id || "",
                    })
                  }
                >
                  Bayar
                </button>
                <button className="text-rose-600 hover:underline text-xs font-semibold" onClick={() => remove(r.id)}>
                  Arsipkan
                </button>
              </div>
            ),
          },
        ]}
      />

      {form && (
        <Modal open onClose={() => setForm(null)} title={kind === "invoice" ? "Buat Faktur Penjualan" : "Buat Tagihan Supplier"}>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Nomor Dokumen">
              <Input value={form.number} onChange={(e) => setForm({ ...form, number: e.target.value })} placeholder="cth: INV/2026/001" />
            </Field>
            <Field label={kind === "invoice" ? "Nama Pelanggan" : "Nama Supplier"}>
              <Input value={form.party_name} onChange={(e) => setForm({ ...form, party_name: e.target.value })} />
            </Field>
            <Field label="Total Nominal (Rp)">
              <Input type="number" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
            </Field>
            <Field label="Tanggal Jatuh Tempo">
              <Input type="date" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} />
            </Field>
            <div className="col-span-2">
              <Field label="Deskripsi">
                <Input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
              </Field>
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-4 mt-4 border-t border-border">
            <Button variant="outline" onClick={() => setForm(null)}>Batal</Button>
            <Button onClick={submit}>Simpan</Button>
          </div>
        </Modal>
      )}

      {payment && (
        <Modal open onClose={() => setPayment(null)} title={payment.kind === "invoice" ? "Terima Pembayaran Invoice" : "Bayar Tagihan Vendor"}>
          <div className="space-y-4">
            <Field label="Nominal Pembayaran (Rp)">
              <Input type="number" value={payment.amount} onChange={(e) => setPayment({ ...payment, amount: e.target.value })} />
            </Field>
            <Field label="Rekening / Akun Kas">
              <Select value={payment.account_id} onChange={(e) => setPayment({ ...payment, account_id: e.target.value })}>
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.code ? `[${a.code}] ` : ""}{a.name}
                  </option>
                ))}
              </Select>
            </Field>
            <div className="flex justify-end gap-2 pt-4 border-t border-border">
              <Button variant="outline" onClick={() => setPayment(null)}>Batal</Button>
              <Button onClick={pay}>Catat Pembayaran</Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ==========================================
// 6. AP / AR (HUTANG & PIUTANG)
// ==========================================
function ApAr() {
  const [data, setData] = useState({ receivables: [], payables: [] });
  useEffect(() => {
    api.get("/finance/ap-ar").then((r) => setData(r.data));
  }, []);

  return (
    <div className="space-y-6">
      <div className="grid md:grid-cols-2 gap-4">
        <Summary title="Total Piutang Berjalan (AR)" value={data.receivables_total} />
        <Summary title="Total Hutang Berjalan (AP)" value={data.payables_total} />
      </div>
      <div className="grid md:grid-cols-2 gap-6">
        <div className="space-y-2">
          <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground">Rincian Piutang Penjualan</h3>
          <DataTable
            rows={data.receivables}
            columns={[
              { header: "Nomor", cell: (r) => <span className="font-mono text-xs">{r.number}</span> },
              { header: "Pelanggan", cell: (r) => r.party_name },
              { header: "Sisa Piutang", cell: (r) => <span className="font-mono font-semibold text-emerald-600">{fmtIDR(Number(r.amount) - Number(r.paid_amount || 0))}</span> },
            ]}
          />
        </div>
        <div className="space-y-2">
          <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground">Rincian Hutang Supplier</h3>
          <DataTable
            rows={data.payables}
            columns={[
              { header: "Nomor", cell: (r) => <span className="font-mono text-xs">{r.number}</span> },
              { header: "Supplier", cell: (r) => r.party_name },
              { header: "Sisa Hutang", cell: (r) => <span className="font-mono font-semibold text-rose-600">{fmtIDR(Number(r.amount) - Number(r.paid_amount || 0))}</span> },
            ]}
          />
        </div>
      </div>
    </div>
  );
}

// ==========================================
// 7. REKONSILIASI BANK
// ==========================================
function BankReconciliation() {
  const { rows } = useCRUD("accounts");
  const [items, setItems] = useState([]);
  useEffect(() => {
    api.get("/finance/reconciliations").then((r) => setItems(r.data));
  }, []);

  return (
    <div className="space-y-6">
      <DataTable
        rows={rows.filter((r) => ["cash", "bank", "wallet", "marketplace"].includes(r.kind) || r.account_type === "asset")}
        columns={[
          { header: "Kode", cell: (r) => <span className="font-mono text-xs">{r.code || "-"}</span> },
          { header: "Nama Rekening", cell: (r) => r.name },
          { header: "Saldo di Sistem", cell: (r) => <b className="font-mono">{fmtIDR(r.balance)}</b> },
          {
            header: "Aksi",
            cell: (r) => <Reconcile account={r} onDone={() => api.get("/finance/reconciliations").then((x) => setItems(x.data))} />,
          },
        ]}
      />
      <div className="space-y-2">
        <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Riwayat Rekonsiliasi</h3>
        <DataTable
          rows={items}
          columns={[
            { header: "Tanggal", cell: (r) => fmtDate(r.created_at) },
            { header: "Akun ID", cell: (r) => <span className="font-mono text-xs">{r.account_id}</span> },
            { header: "Selisih Saldo", cell: (r) => <span className="font-mono font-semibold">{fmtIDR(r.difference)}</span> },
            { header: "Catatan", cell: (r) => r.notes || "-" },
          ]}
        />
      </div>
    </div>
  );
}

function Reconcile({ account, onDone }) {
  const [open, setOpen] = useState(false);
  const [actual, setActual] = useState(account.balance || 0);

  const submit = async () => {
    try {
      await api.post("/finance/reconcile", {
        account_id: account.id,
        actual_balance: Number(actual),
        notes: "Rekonsiliasi mutasi bank/kas",
      });
      toast.success("Rekonsiliasi tersimpan");
      setOpen(false);
      onDone();
    } catch (e) {
      toast.error(formatErr(e.response?.data?.detail));
    }
  };

  return (
    <>
      <button className="text-blue-600 hover:underline text-xs font-semibold" onClick={() => setOpen(true)}>
        Rekonsiliasi
      </button>
      {open && (
        <Modal open onClose={() => setOpen(false)} title={`Rekonsiliasi ${account.name}`}>
          <div className="space-y-4">
            <Field label="Saldo Rekening Koran Aktual (Rp)">
              <Input type="number" value={actual} onChange={(e) => setActual(e.target.value)} />
            </Field>
            <div className="flex justify-end gap-2 pt-3 border-t border-border">
              <Button variant="outline" onClick={() => setOpen(false)}>Batal</Button>
              <Button onClick={submit}>Simpan</Button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}

// ==========================================
// 8. PAJAK (TAX SUMMARY)
// ==========================================
function Tax() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get("/finance/tax-summary");
      setData(res.data);
    } catch (e) {
      toast.error("Gagal menghitung ringkasan pajak");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-lg font-bold">Ringkasan Pajak Pertambahan Nilai (PPN)</h2>
          <p className="text-xs text-muted-foreground">Hitung pajak masukan (pembelian) vs pajak keluaran (penjualan)</p>
        </div>
        <Button onClick={load} disabled={loading}>{loading ? "Menghitung..." : "Hitung Ringkasan Pajak"}</Button>
      </div>

      {data && (
        <div className="grid md:grid-cols-3 gap-4">
          <Summary title="Pajak Keluaran (Penjualan)" value={data.output_tax} />
          <Summary title="Pajak Masukan (Pembelian)" value={data.input_tax} />
          <Summary title="Pajak Kurang / (Lebih) Bayar" value={data.net_tax} />
        </div>
      )}
    </div>
  );
}

function Summary({ title, value }) {
  return (
    <div className="p-5 rounded-xl border border-border bg-card shadow-sm">
      <div className="text-xs font-bold uppercase tracking-wider text-muted-foreground">{title}</div>
      <div className="text-2xl font-black tracking-tight mt-1 font-mono">{fmtIDR(value || 0)}</div>
    </div>
  );
}
