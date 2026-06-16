import { Suspense, lazy } from "react";
import { Link, Navigate, Route, Routes } from "react-router-dom";

import ProtectedRoute from "@/components/auth/ProtectedRoute";
import Layout from "@/components/layout/Layout";
import { useAuth } from "@/context/AuthContext";
import { getHomeRouteByRole } from "@/utils/role-routing";

const BillingPage = lazy(() => import("@/pages/advisor/BillingPage"));
const DashboardPage = lazy(() => import("@/pages/advisor/DashboardPage"));
const GoalsPage = lazy(() => import("@/pages/advisor/GoalsPage"));
const LeadsPage = lazy(() => import("@/pages/advisor/LeadsPage"));
const ProfilePage = lazy(() => import("@/pages/advisor/ProfilePage"));
const SubscriptionPage = lazy(() => import("@/pages/advisor/SubscriptionPage"));

const AdminDashboard = lazy(() => import("@/pages/admin/AdminDashboard"));
const AnalyticsPage = lazy(() => import("@/pages/admin/AnalyticsPage"));
const FirstPurchaseOfferPage = lazy(
  () => import("@/pages/admin/FirstPurchaseOfferPage"),
);
const PlansPage = lazy(() => import("@/pages/admin/PlansPage"));
const ImportsPage = lazy(() => import("@/pages/admin/ImportsPage"));
const LeadInventoryPage = lazy(() => import("@/pages/admin/LeadInventoryPage"));
const LicenseReviewsPage = lazy(() => import("@/pages/admin/LicenseReviewsPage"));
const OrdersPage = lazy(() => import("@/pages/admin/OrdersPage"));
const UserDetailsPage = lazy(() => import("@/pages/admin/UserDetailsPage"));
const UsersPage = lazy(() => import("@/pages/admin/UsersPage"));

const ForgotPasswordPage = lazy(() => import("@/pages/auth/ForgotPasswordPage"));
const LoginPage = lazy(() => import("@/pages/auth/LoginPage"));
const RegisterPage = lazy(() => import("@/pages/auth/RegisterPage"));
const ResetPasswordPage = lazy(() => import("@/pages/auth/ResetPasswordPage"));

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

const RouteLoadingFallback = () => (
  <div className="flex min-h-[60vh] items-center justify-center">
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 shadow-sm">
      Loading...
    </div>
  </div>
);

export const AppRoutes = () => {
  return (
    <Suspense fallback={<RouteLoadingFallback />}>
      <Routes>
        <Route path="/" element={<HomeRedirect />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />

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
              path="/goals"
              element={
                <ProtectedRoute allowedRoles={["advisor"]}>
                  <GoalsPage />
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
              path="/admin/users"
              element={
                <ProtectedRoute allowedRoles={["admin"]}>
                  <UsersPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/users/:userId"
              element={
                <ProtectedRoute allowedRoles={["admin"]}>
                  <UserDetailsPage />
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
              path="/admin/analytics"
              element={
                <ProtectedRoute allowedRoles={["admin"]}>
                  <AnalyticsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/first-purchase-offer"
              element={
                <ProtectedRoute allowedRoles={["admin"]}>
                  <FirstPurchaseOfferPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin/plans"
              element={
                <ProtectedRoute allowedRoles={["admin"]}>
                  <PlansPage />
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
    </Suspense>
  );
};
