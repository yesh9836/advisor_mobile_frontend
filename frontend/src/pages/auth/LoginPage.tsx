import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate } from "react-router-dom";
import { z } from "zod";

import { useAuth } from "@/context/AuthContext";
import { getHomeRouteByRole } from "@/utils/role-routing";

const loginSchema = z.object({
  email: z.email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

const inputClass =
  "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/25";

const LoginPage = () => {
  const { login, user, loading, error, clearError } = useAuth();

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    mode: "onBlur",
  });

  useEffect(() => () => clearError(), [clearError]);

  const onSubmit = async (values: LoginFormValues) => {
    try {
      await login(values);
    } catch (err) {
      setError("root", {
        message: err instanceof Error ? err.message : "Unable to login",
      });
    }
  };

  if (user && !loading) {
    return <Navigate to={getHomeRouteByRole(user.role)} replace />;
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-950 px-4 py-8">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_10%,rgba(14,165,233,0.35),transparent_36%),radial-gradient(circle_at_75%_0%,rgba(16,185,129,0.2),transparent_30%)]" />
      <div className="relative w-full max-w-md rounded-2xl border border-white/10 bg-white/95 p-6 shadow-2xl backdrop-blur">
        <h1 className="font-display text-2xl font-semibold text-slate-900">
          Welcome Back
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Sign in to access your lead dashboard.
        </p>

        {(error || errors.root) && (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {errors.root?.message ?? error}
          </div>
        )}

        <form
          className="mt-5 space-y-4"
          onSubmit={handleSubmit(onSubmit)}
          noValidate
        >
          <div>
            <label
              className="text-sm font-medium text-slate-700"
              htmlFor="email"
            >
              Email
            </label>
            <input
              id="email"
              type="email"
              className={inputClass}
              {...register("email")}
            />
            {errors.email && (
              <p className="mt-1 text-xs text-red-600">
                {errors.email.message}
              </p>
            )}
          </div>

          <div>
            <div className="flex items-center justify-between">
              <label
                className="text-sm font-medium text-slate-700"
                htmlFor="password"
              >
                Password
              </label>
              <Link
                className="text-xs font-semibold text-brand-700 hover:text-brand-600"
                to="/forgot-password"
              >
                Forgot password?
              </Link>
            </div>
            <input
              id="password"
              type="password"
              className={inputClass}
              {...register("password")}
            />
            {errors.password && (
              <p className="mt-1 text-xs text-red-600">
                {errors.password.message}
              </p>
            )}
          </div>

          <button
            type="submit"
            disabled={isSubmitting || loading}
            className="w-full rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-500 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting || loading ? "Signing in..." : "Sign In"}
          </button>
        </form>

        <p className="mt-4 text-sm text-slate-600">
          New here?{" "}
          <Link
            className="font-semibold text-brand-700 hover:text-brand-600"
            to="/register"
          >
            Create an account
          </Link>
        </p>
      </div>
    </div>
  );
};

export default LoginPage;
