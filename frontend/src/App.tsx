import { BrowserRouter, Link, Navigate, Route, Routes } from "react-router-dom";

import ProtectedRoute from "@/components/auth/ProtectedRoute";
import ErrorBoundary from "@/components/common/ErrorBoundary";
import Layout from "@/components/layout/Layout";
import { AuthProvider } from "@/context/AuthContext";
import BillingPage from "@/pages/advisor/BillingPage";
import DashboardPage from "@/pages/advisor/DashboardPage";
import LeadsPage from "@/pages/advisor/LeadsPage";
import ProfilePage from "@/pages/advisor/ProfilePage";
import SubscriptionPage from "@/pages/advisor/SubscriptionPage";
import AdminDashboard from "@/pages/admin/AdminDashboard";
import LoginPage from "@/pages/auth/LoginPage";
import RegisterPage from "@/pages/auth/RegisterPage";

const NotFoundPage = () => (
  <div className="flex min-h-screen items-center justify-center bg-slate-100 p-6">
    <div className="rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm">
      <h1 className="font-display text-2xl font-semibold text-slate-900">
        Page Not Found
      </h1>
      <p className="mt-2 text-sm text-slate-600">
        The route you requested does not exist.
      </p>
      <Link
        to="/dashboard"
        className="mt-4 inline-block rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-500"
      >
        Back to Dashboard
      </Link>
    </div>
  </div>
);

export const AppRoutes = () => {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/leads" element={<LeadsPage />} />
          <Route path="/subscription" element={<SubscriptionPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/billing" element={<BillingPage />} />
          <Route
            path="/admin"
            element={
              <ProtectedRoute allowedRoles={["admin"]}>
                <AdminDashboard />
              </ProtectedRoute>
            }
          />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
};

const App = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <ErrorBoundary>
          <AppRoutes />
        </ErrorBoundary>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
