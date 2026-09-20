import { useState, useEffect } from "react";
import { PageHeader, Field, Input, Select, Button, DataTable, useCRUD, Modal, StatusPill } from "./_shared";
import { api, formatErr, fmtDate } from "@/lib/api";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";
import { useTheme } from "@/contexts/ThemeContext";
import OnboardingWizard from "./OnboardingWizard";
import { APP_CONFIG, getBusinessPreferences, saveBusinessPreferences } from "@/config/appConfig";
import { SUPPORTED_LANGUAGES, t } from "@/lib/i18n";
import { KeyRound, ShieldCheck, UserPlus, UserCheck, UserX } from "lucide-react";

export default function Settings() {
  const { user } = useAuth();
  const { theme, toggle } = useTheme();
  const [tab, setTab] = useState("general");
  const [users, setUsers] = useState([]);
  const [showWizard, setShowWizard] = useState(false);

  const loadUsers = () => {
    if (user?.role === "owner") {
      api.get("/users").then((r) => setUsers(r.data)).catch(() => {});
    }
  };

  useEffect(() => {
    loadUsers();
  }, [user]);

  const { rows: cats, save: saveCat, remove: rmCat } = useCRUD("categories");
  const { rows: mps, save: saveMp, remove: rmMp } = useCRUD("marketplaces");
  const { rows: exCats, save: saveExCat, remove: rmExCat } = useCRUD("expense_categories");
  const [audit, setAudit] = useState([]);
  const [userModal, setUserModal] = useState(null); // create user
  const [editUserModal, setEditUserModal] = useState(null); // edit user
  const [resetPwdModal, setResetPwdModal] = useState(null); // reset password
  const [mpModal, setMpModal] = useState(null);
  const [auditDetail, setAuditDetail] = useState(null);
  const [profile, setProfile] = useState({
    business_name: "",
    currency: "USD",
    locale: "en-US",
    timezone: "UTC",
    tax_enabled: false,
    tax_name: "Tax",
    tax_rate: 0,
    tax_inclusive: false,
  });
  const [savingProfile, setSavingProfile] = useState(false);
  const [backupStatus, setBackupStatus] = useState(null);

  // Change my password state
  const [myPwd, setMyPwd] = useState({ current_password: "", new_password: "", confirm_password: "" });
  const [changingPwd, setChangingPwd] = useState(false);

  useEffect(() => {
    if (user?.role === "owner") api.get("/audit_logs").then((r) => setAudit(r.data));
  }, [user]);
  useEffect(() => {
    api.get("/settings/business-profile").then((r) => setProfile((p) => ({ ...p, ...r.data }))).catch(() => {});
  }, []);
  useEffect(() => {
    if (user?.role === "owner") api.get("/settings/backup-status").then((r) => setBackupStatus(r.data)).catch(() => {});
  }, [user]);

  const tabs = [
    ["general", "General & Keamanan"],
    ["categories", "Categories"],
    ["marketplaces", "Marketplaces"],
    ["expense_categories", "Expense Categories"],
    ...(user?.role === "owner" ? [["users", "Manajemen User"], ["audit", "Audit Log"], ["backup", "Backup"]] : []),
  ];

  const createUser = async () => {
    try {
      await api.post("/users", userModal);
      toast.success("User berhasil dibuat");
      setUserModal(null);
      loadUsers();
    } catch (e) {
      toast.error(formatErr(e.response?.data?.detail));
    }
  };

  const updateUser = async () => {
    try {
      await api.put(`/users/${editUserModal.id}`, {
        name: editUserModal.name,
        role: editUserModal.role,
        status: editUserModal.status,
      });
      toast.success("Data user berhasil diperbarui");
      setEditUserModal(null);
      loadUsers();
    } catch (e) {
      toast.error(formatErr(e.response?.data?.detail));
    }
  };

  const resetPassword = async () => {
    try {
      await api.post(`/users/${resetPwdModal.id}/reset-password`, {
        new_password: resetPwdModal.new_password,
      });
      toast.success(`Password untuk ${resetPwdModal.email} berhasil di-reset`);
      setResetPwdModal(null);
    } catch (e) {
      toast.error(formatErr(e.response?.data?.detail));
    }
  };

  const handleDeleteUser = async (id) => {
    if (!window.confirm("Apakah Anda yakin ingin mengarsipkan user ini?")) return;
    try {
      await api.delete(`/users/${id}`);
      toast.success("User berhasil diarsipkan");
      loadUsers();
    } catch (e) {
      toast.error(formatErr(e.response?.data?.detail));
    }
  };

  const handleToggleStatus = async (r) => {
    const nextStatus = r.status === "inactive" ? "active" : "inactive";
    try {
      await api.put(`/users/${r.id}`, { status: nextStatus });
      toast.success(`Status user diubah menjadi ${nextStatus}`);
      loadUsers();
    } catch (e) {
      toast.error(formatErr(e.response?.data?.detail));
    }
  };

  const handleChangeMyPassword = async (e) => {
    e.preventDefault();
    if (!myPwd.current_password || !myPwd.new_password) {
      toast.error("Semua kolom password wajib diisi");
      return;
    }
    if (myPwd.new_password !== myPwd.confirm_password) {
      toast.error("Konfirmasi password baru tidak cocok");
      return;
    }
    setChangingPwd(true);
    try {
      await api.post("/auth/change-password", {
        current_password: myPwd.current_password,
        new_password: myPwd.new_password,
      });
      toast.success("Password Anda berhasil diubah");
      setMyPwd({ current_password: "", new_password: "", confirm_password: "" });
    } catch (err) {
      toast.error(formatErr(err.response?.data?.detail || "Gagal mengubah password"));
    } finally {
      setChangingPwd(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title={t("settings")} subtitle="Business configuration & security" />
      <div className="flex gap-2 mb-4 flex-wrap">
        {tabs.map(([k, l]) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            data-testid={`settings-tab-${k}`}
            className={`px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all ${
              tab === k
                ? "bg-neutral-900 text-white dark:bg-stone-100 dark:text-stone-900 shadow-sm"
                : "bg-stone-100 hover:bg-stone-200 dark:bg-stone-900 dark:hover:bg-stone-800 text-muted-foreground"
            }`}
          >
            {l}
          </button>
        ))}
      </div>

      {tab === "general" && (
        <div className="grid md:grid-cols-2 gap-6">
          {/* Business Profile Card */}
          <div className="p-6 rounded-xl border border-border bg-card space-y-4">
            <h3 className="font-bold text-base flex items-center gap-2">
              <ShieldCheck size={18} className="text-emerald-600" /> Profil Bisnis
            </h3>
            <div className="space-y-3">
              <Field label={t("businessProfile")}>
                <Input value={profile.business_name} onChange={(e) => setProfile({ ...profile, business_name: e.target.value })} placeholder="Your business name" />
              </Field>
              <Field label={t("language")}>
                <Select value={getBusinessPreferences().language} onChange={(e) => { saveBusinessPreferences({ language: e.target.value }); window.location.reload(); }}>
                  {SUPPORTED_LANGUAGES.map((x) => (<option key={x.value} value={x.value}>{x.label}</option>))}
                </Select>
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Currency"><Input value={profile.currency} onChange={(e) => setProfile({ ...profile, currency: e.target.value.toUpperCase() })} /></Field>
                <Field label="Locale"><Input value={profile.locale} onChange={(e) => setProfile({ ...profile, locale: e.target.value })} /></Field>
              </div>
              <Field label={t("timezone")}>
                <Input value={profile.timezone} onChange={(e) => setProfile({ ...profile, timezone: e.target.value })} placeholder="Asia/Jakarta" />
              </Field>
              <Field label={t("tax")}>
                <div className="flex gap-2">
                  <Input type="number" value={profile.tax_rate} onChange={(e) => setProfile({ ...profile, tax_rate: e.target.value })} />
                  <label className="flex items-center gap-2 text-sm whitespace-nowrap">
                    <input type="checkbox" checked={profile.tax_enabled} onChange={(e) => setProfile({ ...profile, tax_enabled: e.target.checked })} /> Enabled
                  </label>
                </div>
              </Field>
            </div>
            <Button
              disabled={savingProfile || user?.role !== "owner"}
              onClick={async () => {
                setSavingProfile(true);
                try {
                  await api.put("/settings/business-profile", profile);
                  saveBusinessPreferences(profile);
                  toast.success("Business profile saved");
                } catch (e) {
                  toast.error(formatErr(e.response?.data?.detail));
                } finally {
                  setSavingProfile(false);
                }
              }}
            >
              {savingProfile ? "Saving..." : t("save")}
            </Button>
          </div>

          {/* Account Security & Preferences */}
          <div className="space-y-6">
            {/* Change Password Card */}
            <form onSubmit={handleChangeMyPassword} className="p-6 rounded-xl border border-border bg-card space-y-4">
              <h3 className="font-bold text-base flex items-center gap-2">
                <KeyRound size={18} className="text-amber-600" /> Ganti Password Saya
              </h3>
              <p className="text-xs text-muted-foreground">Minimal 8 karakter, wajib kombinasi huruf dan angka.</p>
              <Field label="Password Saat Ini">
                <Input type="password" value={myPwd.current_password} onChange={(e) => setMyPwd({ ...myPwd, current_password: e.target.value })} required />
              </Field>
              <Field label="Password Baru">
                <Input type="password" value={myPwd.new_password} onChange={(e) => setMyPwd({ ...myPwd, new_password: e.target.value })} required />
              </Field>
              <Field label="Konfirmasi Password Baru">
                <Input type="password" value={myPwd.confirm_password} onChange={(e) => setMyPwd({ ...myPwd, confirm_password: e.target.value })} required />
              </Field>
              <Button type="submit" disabled={changingPwd}>
                {changingPwd ? "Menyimpan..." : "Ubah Password"}
              </Button>
            </form>

            {/* Theme & Setup Wizard Card */}
            <div className="p-6 rounded-xl border border-border bg-card space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-bold text-sm">Tema Aplikasi</div>
                  <div className="text-xs text-muted-foreground">Light atau Dark mode</div>
                </div>
                <Button variant="outline" onClick={toggle} data-testid="settings-theme">
                  {theme === "dark" ? "Dark Mode" : "Light Mode"}
                </Button>
              </div>
              <div className="pt-3 border-t border-border flex items-center justify-between">
                <div>
                  <div className="font-bold text-sm">Setup Onboarding Wizard</div>
                  <div className="text-xs text-muted-foreground">Konfigurasi ulang profil & saldo awal</div>
                </div>
                <Button variant="outline" onClick={() => setShowWizard(true)} data-testid="btn-open-wizard">
                  Buka Wizard
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showWizard && <OnboardingWizard onClose={() => setShowWizard(false)} />}

      {tab === "categories" && (
        <SimpleCRUD title="Product Categories" rows={cats} save={saveCat} remove={rmCat} fields={[{ key: "name", label: "Name" }, { key: "kind", label: "Kind" }]} />
      )}
      {tab === "expense_categories" && (
        <SimpleCRUD title="Expense Categories" rows={exCats} save={saveExCat} remove={rmExCat} fields={[{ key: "name", label: "Name" }]} />
      )}

      {tab === "marketplaces" && (
        <div>
          <div className="flex justify-end mb-3">
            <Button onClick={() => setMpModal({ name: "", admin_fee_pct: 0, service_fee_pct: 0, payment_fee_pct: 0 })} data-testid="btn-new-mp">
              + Marketplace
            </Button>
          </div>
          <DataTable
            testid="mp-table"
            rows={mps}
            columns={[
              { header: "Name", cell: (r) => <span className="font-semibold">{r.name}</span> },
              { header: "Admin Fee", cell: (r) => `${r.admin_fee_pct || 0}%` },
              { header: "Service Fee", cell: (r) => `${r.service_fee_pct || 0}%` },
              { header: "Payment Fee", cell: (r) => `${r.payment_fee_pct || 0}%` },
              {
                header: "",
                cell: (r) => (
                  <div className="flex gap-2">
                    <button onClick={() => setMpModal(r)}>Edit</button>
                    <button onClick={() => rmMp(r.id)} className="text-rose-500">Hapus</button>
                  </div>
                ),
              },
            ]}
          />
          {mpModal && (
            <Modal open onClose={() => setMpModal(null)} title="Marketplace">
              <div className="grid grid-cols-2 gap-3">
                <Field label="Name"><Input value={mpModal.name} onChange={(e) => setMpModal({ ...mpModal, name: e.target.value })} /></Field>
                <Field label="Admin Fee %"><Input type="number" step="0.01" value={mpModal.admin_fee_pct} onChange={(e) => setMpModal({ ...mpModal, admin_fee_pct: e.target.value })} /></Field>
                <Field label="Service Fee %"><Input type="number" step="0.01" value={mpModal.service_fee_pct} onChange={(e) => setMpModal({ ...mpModal, service_fee_pct: e.target.value })} /></Field>
                <Field label="Payment Fee %"><Input type="number" step="0.01" value={mpModal.payment_fee_pct} onChange={(e) => setMpModal({ ...mpModal, payment_fee_pct: e.target.value })} /></Field>
              </div>
              <div className="flex justify-end gap-2 mt-6">
                <Button variant="outline" onClick={() => setMpModal(null)}>Batal</Button>
                <Button onClick={async () => { if (await saveMp(mpModal, mpModal.id)) setMpModal(null); }}>Simpan</Button>
              </div>
            </Modal>
          )}
        </div>
      )}

      {/* USER MANAGEMENT TAB */}
      {tab === "users" && (
        <div className="space-y-4">
          <div className="flex justify-between items-center mb-3">
            <div>
              <h3 className="font-bold text-base">Daftar Pengguna & Hak Akses</h3>
              <p className="text-xs text-muted-foreground">Kelola staf, peran (RBAC), status aktif, dan reset password.</p>
            </div>
            <Button onClick={() => setUserModal({ email: "", password: "", name: "", role: "admin" })} data-testid="btn-new-user">
              + Tambah User Baru
            </Button>
          </div>

          <DataTable
            testid="users-table"
            rows={users}
            columns={[
              { header: "Email", cell: (r) => <span className="font-mono text-xs font-semibold">{r.email}</span> },
              { header: "Nama Lengkap", cell: (r) => <span className="font-medium">{r.name}</span> },
              {
                header: "Role / Hak Akses",
                cell: (r) => (
                  <span className={`px-2 py-0.5 text-[10px] uppercase font-bold rounded border ${
                    r.role === "owner" ? "bg-purple-100 text-purple-800 border-purple-300 dark:bg-purple-950 dark:text-purple-300"
                    : r.role === "admin" ? "bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-950 dark:text-blue-300"
                    : r.role === "production" ? "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950 dark:text-amber-300"
                    : "bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-300"
                  }`}>
                    {r.role}
                  </span>
                ),
              },
              {
                header: "Status",
                cell: (r) => <StatusPill status={r.status || "active"} />,
              },
              { header: "Dibuat", cell: (r) => fmtDate(r.created_at) },
              {
                header: "Aksi",
                cell: (r) => (
                  <div className="flex items-center gap-2">
                    <button className="text-blue-600 hover:underline text-xs font-semibold" onClick={() => setEditUserModal({ ...r })}>
                      Edit
                    </button>
                    <button className="text-amber-600 hover:underline text-xs font-semibold" onClick={() => setResetPwdModal({ id: r.id, email: r.email, new_password: "" })}>
                      Reset Pwd
                    </button>
                    {r.id !== user?.id && (
                      <>
                        <button
                          className={`text-xs font-semibold hover:underline ${r.status === "inactive" ? "text-emerald-600" : "text-amber-700"}`}
                          onClick={() => handleToggleStatus(r)}
                        >
                          {r.status === "inactive" ? "Aktifkan" : "Nonaktifkan"}
                        </button>
                        <button className="text-rose-600 hover:underline text-xs font-semibold" onClick={() => handleDeleteUser(r.id)}>
                          Hapus
                        </button>
                      </>
                    )}
                  </div>
                ),
              },
            ]}
          />

          {/* CREATE USER MODAL */}
          {userModal && (
            <Modal open onClose={() => setUserModal(null)} title="Tambah Pengguna Baru">
              <div className="space-y-3">
                <div className="grid sm:grid-cols-2 gap-3">
                  <Field label="Email Pengguna">
                    <Input value={userModal.email} onChange={(e) => setUserModal({ ...userModal, email: e.target.value })} placeholder="nama@perusahaan.com" />
                  </Field>
                  <Field label="Nama Lengkap">
                    <Input value={userModal.name} onChange={(e) => setUserModal({ ...userModal, name: e.target.value })} placeholder="Nama staf" />
                  </Field>
                </div>
                <div className="grid sm:grid-cols-2 gap-3">
                  <Field label="Password (Min. 8 Karakter, Huruf & Angka)">
                    <Input type="password" value={userModal.password} onChange={(e) => setUserModal({ ...userModal, password: e.target.value })} placeholder="Password kuat" />
                  </Field>
                  <Field label="Hak Akses (Role)">
                    <Select value={userModal.role} onChange={(e) => setUserModal({ ...userModal, role: e.target.value })}>
                      <option value="owner">Owner (Akses Seluruh Modul & Settings)</option>
                      <option value="admin">Admin (Katalog, Penjualan, Pembelian, CRM)</option>
                      <option value="production">Production (Produksi, BOM, Inventory Bahan)</option>
                      <option value="finance">Finance (Keuangan, COA, Laporan, Tagihan)</option>
                    </Select>
                  </Field>
                </div>
                <div className="flex justify-end gap-2 pt-4 border-t border-border mt-4">
                  <Button variant="outline" onClick={() => setUserModal(null)}>Batal</Button>
                  <Button onClick={createUser} data-testid="btn-save-user">Simpan Pengguna</Button>
                </div>
              </div>
            </Modal>
          )}

          {/* EDIT USER MODAL */}
          {editUserModal && (
            <Modal open onClose={() => setEditUserModal(null)} title={`Edit Pengguna: ${editUserModal.email}`}>
              <div className="space-y-3">
                <Field label="Nama Lengkap">
                  <Input value={editUserModal.name} onChange={(e) => setEditUserModal({ ...editUserModal, name: e.target.value })} />
                </Field>
                <div className="grid sm:grid-cols-2 gap-3">
                  <Field label="Hak Akses (Role)">
                    <Select value={editUserModal.role} onChange={(e) => setEditUserModal({ ...editUserModal, role: e.target.value })}>
                      <option value="owner">Owner</option>
                      <option value="admin">Admin</option>
                      <option value="production">Production</option>
                      <option value="finance">Finance</option>
                    </Select>
                  </Field>
                  <Field label="Status Akun">
                    <Select value={editUserModal.status || "active"} onChange={(e) => setEditUserModal({ ...editUserModal, status: e.target.value })}>
                      <option value="active">Active (Dapat Login)</option>
                      <option value="inactive">Inactive (Diblokir)</option>
                    </Select>
                  </Field>
                </div>
                <div className="flex justify-end gap-2 pt-4 border-t border-border mt-4">
                  <Button variant="outline" onClick={() => setEditUserModal(null)}>Batal</Button>
                  <Button onClick={updateUser}>Simpan Perubahan</Button>
                </div>
              </div>
            </Modal>
          )}

          {/* RESET PASSWORD MODAL */}
          {resetPwdModal && (
            <Modal open onClose={() => setResetPwdModal(null)} title={`Reset Password: ${resetPwdModal.email}`}>
              <div className="space-y-4">
                <p className="text-xs text-muted-foreground">
                  Masukkan password baru untuk pengguna ini. Minimal 8 karakter dan mengandung kombinasi huruf serta angka.
                </p>
                <Field label="Password Baru">
                  <Input type="password" value={resetPwdModal.new_password} onChange={(e) => setResetPwdModal({ ...resetPwdModal, new_password: e.target.value })} placeholder="Password baru" />
                </Field>
                <div className="flex justify-end gap-2 pt-4 border-t border-border">
                  <Button variant="outline" onClick={() => setResetPwdModal(null)}>Batal</Button>
                  <Button onClick={resetPassword}>Reset Password</Button>
                </div>
              </div>
            </Modal>
          )}
        </div>
      )}

      {tab === "audit" && (
        <DataTable
          testid="audit-table"
          rows={audit}
          columns={[
            { header: "Date", cell: (r) => new Date(r.created_at).toLocaleString("id-ID") },
            { header: "User", cell: (r) => <span className="font-mono text-xs">{r.user_email}</span> },
            {
              header: "Action",
              cell: (r) => (
                <span className={`text-[10px] uppercase font-bold tracking-widest px-2 py-0.5 rounded ${
                  r.action === "login_failed" ? "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300"
                  : r.action === "login_success" ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                  : "bg-stone-100 dark:bg-stone-800"
                }`}>
                  {r.action}
                </span>
              ),
            },
            { header: "Entity", cell: (r) => r.entity },
            { header: "Detail", cell: (r) => <Button variant="outline" onClick={() => setAuditDetail(r)}>Lihat</Button> },
          ]}
        />
      )}

      {tab === "backup" && user?.role === "owner" && (
        <div className="p-6 rounded-lg border border-border bg-card space-y-4">
          <div>
            <div className="font-display font-bold text-lg">Backup status</div>
            <div className="text-sm text-muted-foreground">Backup database dan attachment untuk pemulihan bisnis.</div>
          </div>
          {backupStatus?.warning && <div className="p-3 rounded-md bg-amber-100 text-amber-900 text-sm">{backupStatus.warning}</div>}
          <div className="grid md:grid-cols-3 gap-3">
            <div><div className="text-xs text-muted-foreground">Latest backup</div><div className="font-semibold">{backupStatus?.latest || "Belum ada"}</div></div>
            <div><div className="text-xs text-muted-foreground">Created</div><div className="font-semibold">{backupStatus?.latest_at ? fmtDate(backupStatus.latest_at) : "-"}</div></div>
            <div><div className="text-xs text-muted-foreground">Total backups</div><div className="font-semibold">{backupStatus?.backup_count || 0}</div></div>
          </div>
          <div className="text-sm text-muted-foreground">Jalankan <code>scripts/backup.ps1</code> secara berkala. Uji restore di lingkungan terpisah sebelum mengandalkan backup untuk produksi.</div>
        </div>
      )}

      {auditDetail && (
        <Modal open onClose={() => setAuditDetail(null)} title="Detail Audit">
          <div className="space-y-3 text-sm">
            <div><b>Aksi:</b> {auditDetail.action}</div>
            <div><b>Entity:</b> {auditDetail.entity}</div>
            <div>
              <b>Sebelum:</b>
              <pre className="mt-1 p-3 rounded bg-stone-100 dark:bg-stone-900 overflow-auto text-xs">{JSON.stringify(auditDetail.old_value, null, 2)}</pre>
            </div>
            <div>
              <b>Sesudah:</b>
              <pre className="mt-1 p-3 rounded bg-stone-100 dark:bg-stone-900 overflow-auto text-xs">{JSON.stringify(auditDetail.new_value, null, 2)}</pre>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

function SimpleCRUD({ title, rows, save, remove, fields }) {
  const [edit, setEdit] = useState(null);
  return (
    <div>
      <div className="flex justify-end mb-3">
        <Button onClick={() => setEdit(Object.fromEntries(fields.map((f) => [f.key, ""])))}>+ Tambah</Button>
      </div>
      <DataTable
        rows={rows}
        columns={[
          ...fields.map((f) => ({ header: f.label, cell: (r) => r[f.key] || "-" })),
          {
            header: "",
            cell: (r) => (
              <div className="flex gap-2">
                <button onClick={() => setEdit(r)}>Edit</button>
                <button onClick={() => remove(r.id)} className="text-rose-500">Hapus</button>
              </div>
            ),
          },
        ]}
      />
      {edit && (
        <Modal open onClose={() => setEdit(null)} title={title}>
          <div className="grid grid-cols-2 gap-3">
            {fields.map((f) => (
              <Field key={f.key} label={f.label}>
                <Input value={edit[f.key] || ""} onChange={(e) => setEdit({ ...edit, [f.key]: e.target.value })} />
              </Field>
            ))}
          </div>
          <div className="flex justify-end gap-2 mt-6">
            <Button variant="outline" onClick={() => setEdit(null)}>Batal</Button>
            <Button onClick={async () => { if (await save(edit, edit.id)) setEdit(null); }}>Simpan</Button>
          </div>
        </Modal>
      )}
    </div>
  );
}
