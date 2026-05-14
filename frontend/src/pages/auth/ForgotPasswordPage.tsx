import { zodResolver } from "@hookform/resolvers/zod";
import axios from "axios";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";

import { requestPasswordReset } from "@/api/auth";
import brandLogo from "@/assets/Spectaculeads-logo.jpeg";
import loginBackground from "@/assets/login-background-1920.png";
import { getApiErrorMessage } from "@/utils/api-error";

const forgotPasswordSchema = z.object({
  email: z.email("Enter a valid email"),
});

type ForgotPasswordFormValues = z.infer<typeof forgotPasswordSchema>;

const inputClass =
  "mt-1 w-full rounded-xl border border-[#d8e8ee] bg-white px-3 py-2.5 text-sm text-[#202860] placeholder:text-[#8aa0aa] focus:border-[#18a0b8] focus:outline-none focus:ring-2 focus:ring-[#18a0b8]/25";
const authPageClass =
  "flex min-h-screen items-center justify-center bg-[#182048] bg-cover bg-center bg-no-repeat px-4 py-8";
const authPageStyle = {
  backgroundImage: `url(${loginBackground})`,
};
const authCardClass =
  "w-full max-w-md rounded-2xl border border-[#d8e8ee] border-t-4 border-t-[#18a0b8] bg-white p-6 shadow-[0_24px_60px_rgba(17,23,53,0.35)]";

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
    <div className={authPageClass} style={authPageStyle}>
      <div className={authCardClass}>
        <div className="mb-6">
          <img
            className="h-16 w-auto"
            src={brandLogo}
            alt="SpectacuLeads logo"
          />
          <h1 className="mt-4 font-display text-2xl font-semibold text-[#202860]">
            Forgot Password
          </h1>
          <p className="mt-1 text-sm text-[#58707d]">
            Enter your email and we&apos;ll send a reset link if an account exists.
          </p>
        </div>

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
            <label className="text-sm font-medium text-[#202860]" htmlFor="email">
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
            className="w-full rounded-xl bg-[#202860] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#182048] focus:outline-none focus:ring-2 focus:ring-[#18a0b8]/30 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting
              ? "Sending..."
              : isRateLimited
                ? `Try again in ${rateLimitRemainingSeconds}s`
                : "Send Reset Link"}
          </button>
        </form>

        <p className="mt-4 text-sm text-[#58707d]">
          Remembered your password?{" "}
          <Link className="font-semibold text-[#108da3] hover:text-[#18a0b8]" to="/login">
            Back to login
          </Link>
        </p>
      </div>
    </div>
  );
};

export default ForgotPasswordPage;
