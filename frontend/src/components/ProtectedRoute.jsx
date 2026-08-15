import { Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";

export default function ProtectedRoute({ children, module }) {
  const { user, loading, canAccess } = useAuth();
  if (loading) return <div className="flex items-center justify-center h-screen text-sm text-muted-foreground" data-testid="auth-loading">Memuat...</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (module && !canAccess(module)) {
    return (
      <div className="p-10 text-center" data-testid="access-denied">
        <h2 className="text-2xl font-bold mb-2">Akses Ditolak</h2>
        <p className="text-muted-foreground">Peran <b>{user.role}</b> tidak memiliki akses ke modul ini.</p>
      </div>
    );
  }
  return children;
}
