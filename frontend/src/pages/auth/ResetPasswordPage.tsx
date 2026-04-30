import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { z } from "zod";

import { confirmPasswordReset } from "@/api/auth";
import brandLogo from "@/assets/Spectaculeads-logo.jpeg";
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
  "mt-1 w-full rounded-xl border border-[#d8e8ee] bg-white px-3 py-2.5 text-sm text-[#202860] placeholder:text-[#8aa0aa] focus:border-[#18a0b8] focus:outline-none focus:ring-2 focus:ring-[#18a0b8]/25";
const authPageClass =
  "flex min-h-screen items-center justify-center bg-[#182048] px-4 py-8";
const authCardClass =
  "w-full max-w-md rounded-2xl border border-[#d8e8ee] border-t-4 border-t-[#18a0b8] bg-white p-6 shadow-[0_24px_60px_rgba(17,23,53,0.35)]";

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
      <div className={authPageClass}>
        <div className={authCardClass}>
          <div className="mb-6">
            <img
              className="h-16 w-auto"
              src={brandLogo}
              alt="SpectacuLeads logo"
            />
            <h1 className="mt-4 font-display text-2xl font-semibold text-[#202860]">
              Invalid Reset Link
            </h1>
            <p className="mt-2 text-sm text-[#58707d]">
              This reset link is missing a token. Request a new password reset email.
            </p>
          </div>
          <p className="mt-4 text-sm text-[#58707d]">
            <Link className="font-semibold text-[#108da3] hover:text-[#18a0b8]" to="/forgot-password">
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
    <div className={authPageClass}>
      <div className={authCardClass}>
        <div className="mb-6">
          <img
            className="h-16 w-auto"
            src={brandLogo}
            alt="SpectacuLeads logo"
          />
          <h1 className="mt-4 font-display text-2xl font-semibold text-[#202860]">
            Reset Password
          </h1>
          <p className="mt-1 text-sm text-[#58707d]">
            Choose a new password for your account.
          </p>
        </div>

        {errors.root && (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {errors.root.message}
          </div>
        )}

        <form className="mt-5 space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
          <div>
            <label className="text-sm font-medium text-[#202860]" htmlFor="password">
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
            <label className="text-sm font-medium text-[#202860]" htmlFor="confirmPassword">
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
            className="w-full rounded-xl bg-[#202860] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#182048] focus:outline-none focus:ring-2 focus:ring-[#18a0b8]/30 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? "Updating..." : "Update Password"}
          </button>
        </form>

        <p className="mt-4 text-sm text-[#58707d]">
          <Link className="font-semibold text-[#108da3] hover:text-[#18a0b8]" to="/login">
            Back to login
          </Link>
        </p>
      </div>
    </div>
  );
};

export default ResetPasswordPage;
