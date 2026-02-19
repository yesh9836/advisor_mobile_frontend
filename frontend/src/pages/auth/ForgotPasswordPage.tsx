import { zodResolver } from "@hookform/resolvers/zod";
import axios from "axios";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";

import { requestPasswordReset } from "@/api/auth";
import { getApiErrorMessage } from "@/utils/api-error";

const forgotPasswordSchema = z.object({
  email: z.email("Enter a valid email"),
});

type ForgotPasswordFormValues = z.infer<typeof forgotPasswordSchema>;

const inputClass =
  "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/25";

const ForgotPasswordPage = () => {
  const [serverMessage, setServerMessage] = useState<string | null>(null);
  const [rateLimitRemainingSeconds, setRateLimitRemainingSeconds] = useState(0);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    clearErrors,
    setError,
  } = useForm<ForgotPasswordFormValues>({
    resolver: zodResolver(forgotPasswordSchema),
    mode: "onBlur",
  });

  const isRateLimited = rateLimitRemainingSeconds > 0;

  useEffect(() => {
    if (!isRateLimited) {
      return;
    }

    const timerId = window.setInterval(() => {
      setRateLimitRemainingSeconds((current) => (current <= 1 ? 0 : current - 1));
    }, 1000);

    return () => window.clearInterval(timerId);
  }, [isRateLimited]);

  const onSubmit = async (values: ForgotPasswordFormValues) => {
    if (isRateLimited) {
      return;
    }

    setServerMessage(null);
    clearErrors("root");

    try {
      const response = await requestPasswordReset(values.email);
      setServerMessage(response.message);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 429) {
        const retryAfterHeader = err.response.headers?.["retry-after"];
        const retryAfterRaw = Array.isArray(retryAfterHeader)
          ? retryAfterHeader[0]
          : retryAfterHeader;
        const retryAfterSeconds = Number.parseInt(String(retryAfterRaw ?? "0"), 10);
        if (Number.isFinite(retryAfterSeconds) && retryAfterSeconds > 0) {
          setRateLimitRemainingSeconds(retryAfterSeconds);
        }
      }

      setError("root", {
        message: getApiErrorMessage(
          err,
          "Unable to process password reset right now.",
        ),
      });
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-slate-950 px-4 py-8">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_10%,rgba(14,165,233,0.35),transparent_36%),radial-gradient(circle_at_75%_0%,rgba(16,185,129,0.2),transparent_30%)]" />
      <div className="relative w-full max-w-md rounded-2xl border border-white/10 bg-white/95 p-6 shadow-2xl backdrop-blur">
        <h1 className="font-display text-2xl font-semibold text-slate-900">
          Forgot Password
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Enter your email and we&apos;ll send a reset link if an account exists.
        </p>

        {errors.root && (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {errors.root.message}
          </div>
        )}

        {isRateLimited && (
          <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            Too many reset attempts. Please try again in{" "}
            <span className="font-semibold">{rateLimitRemainingSeconds}s</span>.
          </div>
        )}

        {serverMessage && (
          <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            {serverMessage}
          </div>
        )}

        <form className="mt-5 space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
          <div>
            <label className="text-sm font-medium text-slate-700" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              className={inputClass}
              {...register("email")}
            />
            {errors.email && (
              <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>
            )}
          </div>

          <button
            type="submit"
            disabled={isSubmitting || isRateLimited}
            className="w-full rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-500 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting
              ? "Sending..."
              : isRateLimited
                ? `Try again in ${rateLimitRemainingSeconds}s`
                : "Send Reset Link"}
          </button>
        </form>

        <p className="mt-4 text-sm text-slate-600">
          Remembered your password?{" "}
          <Link className="font-semibold text-brand-700 hover:text-brand-600" to="/login">
            Back to login
          </Link>
        </p>
      </div>
    </div>
  );
};

export default ForgotPasswordPage;
