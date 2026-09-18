import { useState, useEffect } from "react";
import { PageHeader, Field, Input, Select, Button, DataTable, useCRUD, Modal } from "./_shared";
import { api, formatErr, fmtDate } from "@/lib/api";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";
import { useTheme } from "@/contexts/ThemeContext";
import OnboardingWizard from "./OnboardingWizard";
import { APP_CONFIG, getBusinessPreferences, saveBusinessPreferences } from "@/config/appConfig";
import { SUPPORTED_LANGUAGES, t } from "@/lib/i18n";

export default function Settings() {
  const { user } = useAuth();
  const { theme, toggle } = useTheme();
  const [tab, setTab] = useState("general");
  const [users, setUsers] = useState([]);
  const [showWizard, setShowWizard] = useState(false);
  useEffect(() => {
    if (user?.role === "owner") api.get("/users").then(r => setUsers(r.data)).catch(() => {});
  }, [user]);
  const { rows: cats, save: saveCat, remove: rmCat } = useCRUD("categories");
  const { rows: mps, save: saveMp, remove: rmMp } = useCRUD("marketplaces");
  const { rows: exCats, save: saveExCat, remove: rmExCat } = useCRUD("expense_categories");
  const [audit, setAudit] = useState([]);
  const [userModal, setUserModal] = useState(null);
  const [mpModal, setMpModal] = useState(null);
  const [auditDetail, setAuditDetail] = useState(null);
  const [profile, setProfile] = useState({ business_name:"", currency:"USD", locale:"en-US", timezone:"UTC", tax_enabled:false, tax_name:"Tax", tax_rate:0, tax_inclusive:false });
  const [savingProfile, setSavingProfile] = useState(false);

  useEffect(() => { if (user?.role === "owner") api.get("/audit_logs").then(r=>setAudit(r.data)); }, [user]);
  useEffect(() => { api.get("/settings/business-profile").then(r=>setProfile(p=>({...p,...r.data}))).catch(()=>{}); }, []);

  const tabs = [
    ["general","General"],["categories","Categories"],["marketplaces","Marketplaces"],["expense_categories","Expense Categories"],
    ...(user?.role==="owner"?[["users","Users"],["audit","Audit Log"]]:[]),
  ];

  const createUser = async () => {
    try {
      await api.post("/users", userModal);
      toast.success("User dibuat");
      setUserModal(null);
      window.location.reload();
    } catch (e) { toast.error(formatErr(e.response?.data?.detail)); }
  };

  return (
    <div>
      <PageHeader title={t("settings")} subtitle="Business configuration"/>
      <div className="flex gap-2 mb-4 flex-wrap">
        {tabs.map(([k,l])=>(
          <button key={k} onClick={()=>setTab(k)} data-testid={`settings-tab-${k}`}
            className={`px-4 py-2 rounded-md text-xs font-semibold uppercase tracking-widest ${tab===k?"bg-neutral-900 text-white dark:bg-stone-100 dark:text-stone-900":"bg-stone-100 dark:bg-stone-900"}`}>{l}</button>
        ))}
      </div>

      {tab==="general" && (
        <div className="p-6 rounded-lg border border-border bg-card space-y-4">
          <div className="grid md:grid-cols-2 gap-4">
            <Field label={t("businessProfile")}><Input value={profile.business_name} onChange={e=>setProfile({...profile,business_name:e.target.value})} placeholder="Your business name"/></Field>
            <Field label={t("language")}><Select value={getBusinessPreferences().language} onChange={e=>{saveBusinessPreferences({language:e.target.value}); window.location.reload();}}>{SUPPORTED_LANGUAGES.map(x=><option key={x.value} value={x.value}>{x.label}</option>)}</Select></Field>
            <Field label="Currency"><Input value={profile.currency} onChange={e=>setProfile({...profile,currency:e.target.value.toUpperCase()})}/></Field>
            <Field label="Locale"><Input value={profile.locale} onChange={e=>setProfile({...profile,locale:e.target.value})}/></Field>
            <Field label={t("timezone")}><Input value={profile.timezone} onChange={e=>setProfile({...profile,timezone:e.target.value})} placeholder="Asia/Jakarta"/></Field>
            <Field label={t("tax")}><div className="flex gap-2"><Input type="number" value={profile.tax_rate} onChange={e=>setProfile({...profile,tax_rate:e.target.value})}/><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={profile.tax_enabled} onChange={e=>setProfile({...profile,tax_enabled:e.target.checked})}/> Enabled</label></div></Field>
          </div>
          <Button disabled={savingProfile || user?.role !== "owner"} onClick={async()=>{setSavingProfile(true);try{await api.put("/settings/business-profile",profile);saveBusinessPreferences(profile);toast.success("Business profile saved");}catch(e){toast.error(formatErr(e.response?.data?.detail));}finally{setSavingProfile(false);}}}>{savingProfile ? "Saving..." : t("save")}</Button>
          <div className="flex items-center justify-between">
            <div><div className="font-display font-bold">Theme</div><div className="text-sm text-muted-foreground">Light atau Dark mode</div></div>
            <Button variant="outline" onClick={toggle} data-testid="settings-theme">{theme==="dark"?"Dark":"Light"}</Button>
          </div>
          <div className="pt-3 border-t border-border flex items-center justify-between">
            <div><div className="font-display font-bold">Setup Wizard</div><div className="text-sm text-muted-foreground">Konfigurasi ulang business profile & modal awal</div></div>
            <Button variant="outline" onClick={()=>setShowWizard(true)} data-testid="btn-open-wizard">Buka Wizard</Button>
          </div>
          <div className="pt-3 border-t border-border">
            <div className="font-display font-bold mb-1">Business Profile</div>
            <div className="text-sm text-muted-foreground">{APP_CONFIG.name} · Small Business Operations · Currency: {getBusinessPreferences().currency}</div>
          </div>
        </div>
      )}
      {showWizard && <OnboardingWizard onClose={()=>setShowWizard(false)} />}

      {tab==="categories" && <SimpleCRUD title="Product Categories" rows={cats} save={saveCat} remove={rmCat} fields={[{key:"name",label:"Name"},{key:"kind",label:"Kind"}]}/>}
      {tab==="expense_categories" && <SimpleCRUD title="Expense Categories" rows={exCats} save={saveExCat} remove={rmExCat} fields={[{key:"name",label:"Name"}]}/>}

      {tab==="marketplaces" && (
        <div>
          <div className="flex justify-end mb-3"><Button onClick={()=>setMpModal({name:"",admin_fee_pct:0,service_fee_pct:0,payment_fee_pct:0})} data-testid="btn-new-mp">+ Marketplace</Button></div>
          <DataTable testid="mp-table" rows={mps}
            columns={[
              {header:"Name",cell:r=><span className="font-semibold">{r.name}</span>},
              {header:"Admin Fee",cell:r=>`${r.admin_fee_pct||0}%`},
              {header:"Service Fee",cell:r=>`${r.service_fee_pct||0}%`},
              {header:"Payment Fee",cell:r=>`${r.payment_fee_pct||0}%`},
              {header:"",cell:r=>(<div className="flex gap-2"><button onClick={()=>setMpModal(r)}>Edit</button><button onClick={()=>rmMp(r.id)} className="text-rose-500">Hapus</button></div>)},
            ]}/>
          {mpModal && <Modal open onClose={()=>setMpModal(null)} title="Marketplace">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Name"><Input value={mpModal.name} onChange={e=>setMpModal({...mpModal,name:e.target.value})}/></Field>
              <Field label="Admin Fee %"><Input type="number" step="0.01" value={mpModal.admin_fee_pct} onChange={e=>setMpModal({...mpModal,admin_fee_pct:e.target.value})}/></Field>
              <Field label="Service Fee %"><Input type="number" step="0.01" value={mpModal.service_fee_pct} onChange={e=>setMpModal({...mpModal,service_fee_pct:e.target.value})}/></Field>
              <Field label="Payment Fee %"><Input type="number" step="0.01" value={mpModal.payment_fee_pct} onChange={e=>setMpModal({...mpModal,payment_fee_pct:e.target.value})}/></Field>
            </div>
            <div className="flex justify-end gap-2 mt-6"><Button variant="outline" onClick={()=>setMpModal(null)}>Batal</Button><Button onClick={async()=>{ if (await saveMp(mpModal, mpModal.id)) setMpModal(null); }}>Simpan</Button></div>
          </Modal>}
        </div>
      )}

      {tab==="users" && (
        <div>
          <div className="flex justify-end mb-3"><Button onClick={()=>setUserModal({email:"",password:"",name:"",role:"admin"})} data-testid="btn-new-user">+ User</Button></div>
          <DataTable testid="users-table" rows={users}
            columns={[
              {header:"Email",cell:r=><span className="font-mono text-xs">{r.email}</span>},
              {header:"Name",cell:r=><span className="font-semibold">{r.name}</span>},
              {header:"Role",cell:r=><span className="text-[10px] uppercase font-bold tracking-widest">{r.role}</span>},
              {header:"Created",cell:r=>fmtDate(r.created_at)},
            ]}/>
          {userModal && <Modal open onClose={()=>setUserModal(null)} title="User Baru">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Email"><Input value={userModal.email} onChange={e=>setUserModal({...userModal,email:e.target.value})}/></Field>
              <Field label="Password"><Input type="password" value={userModal.password} onChange={e=>setUserModal({...userModal,password:e.target.value})}/></Field>
              <Field label="Name"><Input value={userModal.name} onChange={e=>setUserModal({...userModal,name:e.target.value})}/></Field>
              <Field label="Role"><Select value={userModal.role} onChange={e=>setUserModal({...userModal,role:e.target.value})}>
                <option value="owner">Owner</option><option value="admin">Admin</option>
                <option value="production">Production</option><option value="finance">Finance</option>
              </Select></Field>
            </div>
            <div className="flex justify-end gap-2 mt-6"><Button variant="outline" onClick={()=>setUserModal(null)}>Batal</Button><Button onClick={createUser} data-testid="btn-save-user">Simpan</Button></div>
          </Modal>}
        </div>
      )}

      {tab==="audit" && (
        <DataTable testid="audit-table" rows={audit}
          columns={[
            {header:"Date",cell:r=>new Date(r.created_at).toLocaleString("id-ID")},
            {header:"User",cell:r=><span className="font-mono text-xs">{r.user_email}</span>},
            {header:"Action",cell:r=><span className="text-[10px] uppercase font-bold tracking-widest">{r.action}</span>},
            {header:"Entity",cell:r=>r.entity},
            {header:"Detail",cell:r=><Button variant="outline" onClick={()=>setAuditDetail(r)}>Lihat</Button>},
          ]}/>
      )}
      {auditDetail && <Modal open onClose={()=>setAuditDetail(null)} title="Detail Audit">
        <div className="space-y-3 text-sm"><div><b>Aksi:</b> {auditDetail.action}</div><div><b>Entity:</b> {auditDetail.entity}</div><div><b>Sebelum:</b><pre className="mt-1 p-3 rounded bg-stone-100 dark:bg-stone-900 overflow-auto text-xs">{JSON.stringify(auditDetail.old_value, null, 2)}</pre></div><div><b>Sesudah:</b><pre className="mt-1 p-3 rounded bg-stone-100 dark:bg-stone-900 overflow-auto text-xs">{JSON.stringify(auditDetail.new_value, null, 2)}</pre></div></div>
      </Modal>}
    </div>
  );
}

function SimpleCRUD({ title, rows, save, remove, fields }) {
  const [edit, setEdit] = useState(null);
  return (
    <div>
      <div className="flex justify-end mb-3"><Button onClick={()=>setEdit(Object.fromEntries(fields.map(f=>[f.key,""])))}>+ Tambah</Button></div>
      <DataTable rows={rows}
        columns={[
          ...fields.map(f=>({header:f.label,cell:r=>r[f.key]||"-"})),
          {header:"",cell:r=>(<div className="flex gap-2"><button onClick={()=>setEdit(r)}>Edit</button><button onClick={()=>remove(r.id)} className="text-rose-500">Hapus</button></div>)},
        ]}/>
      {edit && <Modal open onClose={()=>setEdit(null)} title={title}>
        <div className="grid grid-cols-2 gap-3">
          {fields.map(f=><Field key={f.key} label={f.label}><Input value={edit[f.key]||""} onChange={e=>setEdit({...edit,[f.key]:e.target.value})}/></Field>)}
        </div>
        <div className="flex justify-end gap-2 mt-6"><Button variant="outline" onClick={()=>setEdit(null)}>Batal</Button><Button onClick={async()=>{ if (await save(edit, edit.id)) setEdit(null); }}>Simpan</Button></div>
      </Modal>}
    </div>
  );
}
