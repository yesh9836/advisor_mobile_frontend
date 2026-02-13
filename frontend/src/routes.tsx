import { Link, Navigate, Route, Routes } from "react-router-dom";

import ProtectedRoute from "@/components/auth/ProtectedRoute";
import Layout from "@/components/layout/Layout";
import { useAuth } from "@/context/AuthContext";
import BillingPage from "@/pages/advisor/BillingPage";
import DashboardPage from "@/pages/advisor/DashboardPage";
import LeadsPage from "@/pages/advisor/LeadsPage";
import ProfilePage from "@/pages/advisor/ProfilePage";
import SubscriptionPage from "@/pages/advisor/SubscriptionPage";
import AdminDashboard from "@/pages/admin/AdminDashboard";
import ImportsPage from "@/pages/admin/ImportsPage";
import LeadInventoryPage from "@/pages/admin/LeadInventoryPage";
import LicenseReviewsPage from "@/pages/admin/LicenseReviewsPage";
import OrdersPage from "@/pages/admin/OrdersPage";
import LoginPage from "@/pages/auth/LoginPage";
import RegisterPage from "@/pages/auth/RegisterPage";
import { getHomeRouteByRole } from "@/utils/role-routing";

const HomeRedirect = () => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 shadow-sm">
          Loading...
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <Navigate to={getHomeRouteByRole(user.role)} replace />;
};

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
        to="/"
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
      <Route path="/" element={<HomeRedirect />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute allowedRoles={["advisor"]}>
                <DashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/leads"
            element={
              <ProtectedRoute allowedRoles={["advisor"]}>
                <LeadsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/subscription"
            element={
              <ProtectedRoute allowedRoles={["advisor"]}>
                <SubscriptionPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/profile"
            element={
              <ProtectedRoute allowedRoles={["advisor"]}>
                <ProfilePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/billing"
            element={
              <ProtectedRoute allowedRoles={["advisor"]}>
                <BillingPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <ProtectedRoute allowedRoles={["admin"]}>
                <AdminDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/lead-inventory"
            element={
              <ProtectedRoute allowedRoles={["admin"]}>
                <LeadInventoryPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/orders"
            element={
              <ProtectedRoute allowedRoles={["admin"]}>
                <OrdersPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/imports"
            element={
              <ProtectedRoute allowedRoles={["admin"]}>
                <ImportsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/license-reviews"
            element={
              <ProtectedRoute allowedRoles={["admin"]}>
                <LicenseReviewsPage />
              </ProtectedRoute>
            }
          />
        </Route>
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
};
