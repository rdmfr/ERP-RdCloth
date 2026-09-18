import { useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useNavigate } from "react-router-dom";
import { formatErr } from "@/lib/api";
import { toast } from "sonner";
import { APP_CONFIG } from "@/config/appConfig";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [pwd, setPwd] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, pwd);
      toast.success("Selamat datang kembali");
      nav("/");
    } catch (err) {
      toast.error(formatErr(err.response?.data?.detail) || "Login gagal");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-stone-50 dark:bg-stone-950">
      <div className="hidden lg:flex flex-col justify-between p-12 bg-neutral-900 text-white">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-md bg-white text-neutral-900 flex items-center justify-center font-black font-display">Rd</div>
          <span className="font-display font-bold text-lg">{APP_CONFIG.shortName}</span>
        </div>
        <div>
          <h1 className="font-display font-black text-5xl leading-none tracking-tighter mb-6">Business command center<br/>for apparel makers.</h1>
          <p className="text-stone-400 max-w-md leading-relaxed">{APP_CONFIG.tagline}</p>
        </div>
        <div className="text-xs uppercase tracking-widest text-stone-500">v1.0 · Phase 1 Release</div>
      </div>
      <div className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm space-y-6" data-testid="login-form">
          <div>
            <div className="text-xs uppercase tracking-[0.25em] text-muted-foreground mb-2">Masuk</div>
            <h2 className="font-display font-bold text-3xl tracking-tight">{APP_CONFIG.name}</h2>
            <p className="text-sm text-muted-foreground mt-1">Sign in to manage your business workspace.</p>
          </div>
          <div className="space-y-3">
            <div>
              <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Email</label>
              <input data-testid="login-email" value={email} onChange={(e)=>setEmail(e.target.value)} className="w-full mt-1 px-3 py-2.5 bg-white dark:bg-stone-900 border border-border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-neutral-900 dark:focus:ring-stone-100" />
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Password</label>
              <input data-testid="login-password" type="password" value={pwd} onChange={(e)=>setPwd(e.target.value)} className="w-full mt-1 px-3 py-2.5 bg-white dark:bg-stone-900 border border-border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-neutral-900 dark:focus:ring-stone-100" />
            </div>
          </div>
          <button data-testid="login-submit" disabled={loading} className="w-full py-2.5 rounded-md bg-neutral-900 dark:bg-stone-100 text-white dark:text-stone-900 font-semibold text-sm hover:opacity-90 transition-opacity disabled:opacity-50">
            {loading ? "Memuat..." : "Masuk"}
          </button>
        </form>
      </div>
    </div>
  );
}
