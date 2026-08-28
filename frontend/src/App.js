import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/contexts/AuthContext";
import { ThemeProvider } from "@/contexts/ThemeContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import Layout from "@/components/Layout";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Products from "@/pages/Products";
import { Inventory, Suppliers, Customers, Assets, Materials, MarketplaceSettings } from "@/pages/MasterPages";
import { Purchasing, Production } from "@/pages/Operations";
import { Sales, Finance, MarketplaceSettlement, Returns } from "@/pages/Transactions";
import { HPPCalculator, PricingSimulator, BEPCalculator, Reports, DTFCosting } from "@/pages/Calculators";
import Settings from "@/pages/Settings";
import MarketplaceImport from "@/pages/MarketplaceImport";
import OnboardingWizard, { useOnboardingStatus } from "@/pages/OnboardingWizard";
import "@/index.css";

function Shell({ children, module }) {
  return (
    <ProtectedRoute module={module}>
      <Layout>{children}</Layout>
    </ProtectedRoute>
  );
}

function AppRoutes() {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex items-center justify-center h-screen text-sm text-muted-foreground">Memuat...</div>;
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
      <Route path="/" element={<Shell module="dashboard"><Dashboard/></Shell>}/>
      <Route path="/sales" element={<Shell module="sales"><Sales/></Shell>}/>
      <Route path="/products" element={<Shell module="products"><Products/></Shell>}/>
      <Route path="/materials" element={<Shell module="materials"><Materials/></Shell>}/>
      <Route path="/inventory" element={<Shell module="inventory"><Inventory/></Shell>}/>
      <Route path="/purchasing" element={<Shell module="purchasing"><Purchasing/></Shell>}/>
      <Route path="/production" element={<Shell module="production"><Production/></Shell>}/>
      <Route path="/suppliers" element={<Shell module="suppliers"><Suppliers/></Shell>}/>
      <Route path="/customers" element={<Shell module="customers"><Customers/></Shell>}/>
      <Route path="/finance" element={<Shell module="finance"><Finance/></Shell>}/>
      <Route path="/settlements" element={<Shell module="finance"><MarketplaceSettlement/></Shell>}/>
      <Route path="/returns" element={<Shell module="sales"><Returns/></Shell>}/>
      <Route path="/marketplace-settings" element={<Shell module="finance"><MarketplaceSettings/></Shell>}/>
      <Route path="/reports" element={<Shell module="reports"><Reports/></Shell>}/>
      <Route path="/pricing" element={<Shell module="dashboard"><PricingCombined/></Shell>}/>
      <Route path="/dtf-costing" element={<Shell module="production"><DTFCosting/></Shell>}/>
      <Route path="/bep" element={<Shell module="dashboard"><BEPCalculator/></Shell>}/>
      <Route path="/assets" element={<Shell module="assets"><Assets/></Shell>}/>
      <Route path="/settings" element={<Shell module="dashboard"><Settings/></Shell>}/>
      <Route path="/marketplace-import" element={<Shell module="sales"><MarketplaceImport/></Shell>}/>
      <Route path="*" element={<Navigate to="/" replace/>}/>
    </Routes>
  );
}

function PricingCombined() {
  return (
    <div className="space-y-8">
      <DTFCosting/>
      <HPPCalculator/>
      <PricingSimulator/>
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Toaster position="top-right" richColors closeButton />
          <AppRoutes />
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
