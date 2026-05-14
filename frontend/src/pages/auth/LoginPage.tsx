import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate } from "react-router-dom";
import { z } from "zod";

import brandLogo from "@/assets/Spectaculeads-logo.jpeg";
import loginBackground from "@/assets/login-background-1920.png";
import { useAuth } from "@/context/AuthContext";
import { getHomeRouteByRole } from "@/utils/role-routing";

const loginSchema = z.object({
  email: z.email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

const inputClass =
  "mt-1 w-full rounded-xl border border-[#d8e8ee] bg-white px-3 py-2.5 text-sm text-[#202860] placeholder:text-[#8aa0aa] focus:border-[#18a0b8] focus:outline-none focus:ring-2 focus:ring-[#18a0b8]/25";
const authPageClass =
  "flex min-h-screen items-center justify-center bg-[#182048] bg-cover bg-center bg-no-repeat px-4 py-8";
const authPageStyle = {
  backgroundImage: `url(${loginBackground})`,
};
const authCardClass =
  "w-full max-w-md rounded-2xl border border-[#d8e8ee] border-t-4 border-t-[#18a0b8] bg-white p-6 shadow-[0_24px_60px_rgba(17,23,53,0.35)]";

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
    <div className={authPageClass} style={authPageStyle}>
      <div className={authCardClass}>
        <div className="mb-6">
          <img
            className="h-16 w-auto"
            src={brandLogo}
            alt="SpectacuLeads logo"
          />
          <h1 className="mt-4 font-display text-2xl font-semibold text-[#202860]">
            Welcome Back
          </h1>
          <p className="mt-1 text-sm text-[#58707d]">
            Sign in to access your lead dashboard.
          </p>
        </div>

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
              className="text-sm font-medium text-[#202860]"
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
                className="text-sm font-medium text-[#202860]"
                htmlFor="password"
              >
                Password
              </label>
              <Link
                className="text-xs font-semibold text-[#108da3] hover:text-[#18a0b8]"
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
            className="w-full rounded-xl bg-[#202860] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#182048] focus:outline-none focus:ring-2 focus:ring-[#18a0b8]/30 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting || loading ? "Signing in..." : "Sign In"}
          </button>
        </form>

        <p className="mt-4 text-sm text-[#58707d]">
          New here?{" "}
          <Link
            className="font-semibold text-[#108da3] hover:text-[#18a0b8]"
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
