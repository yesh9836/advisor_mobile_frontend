import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { z } from "zod";

import { confirmPasswordReset } from "@/api/auth";
import { getApiErrorMessage } from "@/utils/api-error";

const resetPasswordSchema = z
  .object({
    password: z.string().min(8, "Password must be at least 8 characters"),
    confirmPassword: z.string().min(8, "Confirm your password"),
  })
  .refine((values) => values.password === values.confirmPassword, {
    path: ["confirmPassword"],
    message: "Passwords must match",
  });

type ResetPasswordFormValues = z.infer<typeof resetPasswordSchema>;

const inputClass =
  "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/25";

const ResetPasswordPage = () => {
  const [searchParams] = useSearchParams();
  const [completed, setCompleted] = useState(false);
  const token = searchParams.get("token")?.trim() ?? "";

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(resetPasswordSchema),
    mode: "onBlur",
  });

  if (!token) {
    return (
      <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-950 px-4 py-8">
        <div className="relative w-full max-w-md rounded-2xl border border-white/10 bg-white/95 p-6 shadow-2xl backdrop-blur">
          <h1 className="font-display text-2xl font-semibold text-slate-900">
            Invalid Reset Link
          </h1>
          <p className="mt-2 text-sm text-slate-600">
            This reset link is missing a token. Request a new password reset email.
          </p>
          <p className="mt-4 text-sm text-slate-600">
            <Link className="font-semibold text-brand-700 hover:text-brand-600" to="/forgot-password">
              Request a new reset link
            </Link>
          </p>
        </div>
      </div>
    );
  }

  if (completed) {
    return <Navigate to="/login" replace />;
  }

  const onSubmit = async (values: ResetPasswordFormValues) => {
    try {
      await confirmPasswordReset({
        token,
        new_password: values.password,
      });
      setCompleted(true);
    } catch (err) {
      setError("root", {
        message: getApiErrorMessage(err, "Unable to reset password right now."),
      });
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-950 px-4 py-8">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_10%,rgba(14,165,233,0.35),transparent_36%),radial-gradient(circle_at_75%_0%,rgba(16,185,129,0.2),transparent_30%)]" />
      <div className="relative w-full max-w-md rounded-2xl border border-white/10 bg-white/95 p-6 shadow-2xl backdrop-blur">
        <h1 className="font-display text-2xl font-semibold text-slate-900">
          Reset Password
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Choose a new password for your account.
        </p>

        {errors.root && (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {errors.root.message}
          </div>
        )}

        <form className="mt-5 space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
          <div>
            <label className="text-sm font-medium text-slate-700" htmlFor="password">
              New password
            </label>
            <input
              id="password"
              type="password"
              className={inputClass}
              {...register("password")}
            />
            {errors.password && (
              <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>
            )}
          </div>

          <div>
            <label className="text-sm font-medium text-slate-700" htmlFor="confirmPassword">
              Confirm password
            </label>
            <input
              id="confirmPassword"
              type="password"
              className={inputClass}
              {...register("confirmPassword")}
            />
            {errors.confirmPassword && (
              <p className="mt-1 text-xs text-red-600">
                {errors.confirmPassword.message}
              </p>
            )}
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-500 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? "Updating..." : "Update Password"}
          </button>
        </form>

        <p className="mt-4 text-sm text-slate-600">
          <Link className="font-semibold text-brand-700 hover:text-brand-600" to="/login">
            Back to login
          </Link>
        </p>
      </div>
    </div>
  );
};

export default ResetPasswordPage;
