import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { z } from "zod";

import brandLogo from "@/assets/Spectaculeads-logo.jpeg";
import loginBackground from "@/assets/login-background-1920.png";
import { useAuth } from "@/context/AuthContext";
import { getHomeRouteByRole } from "@/utils/role-routing";

const normalizeUsPhoneInput = (value: string): string => {
  const digits = value.replace(/\D/g, "");
  const localDigits = digits.startsWith("1") ? digits.slice(1) : digits;
  return `+1${localDigits.slice(0, 10)}`;
};

const registerSchema = z
  .object({
    name: z.string().min(2, "Name must be at least 2 characters"),
    email: z.email("Enter a valid email"),
    phone: z
      .string()
      .trim()
      .optional()
      .or(z.literal(""))
      .refine(
        (value) => {
          const normalized = value?.trim() ?? "";
          return !normalized || normalized === "+1" || /^\+1\d{10}$/.test(normalized);
        },
        "Enter a valid US phone number",
      ),
    password: z.string().min(8, "Password must be at least 8 characters"),
    confirmPassword: z.string().min(8, "Confirm your password"),
  })
  .refine((data) => data.password === data.confirmPassword, {
    path: ["confirmPassword"],
    message: "Passwords do not match",
  });

type RegisterFormValues = z.infer<typeof registerSchema>;

const inputClass =
  "mt-1 w-full rounded-xl border border-[#d8e8ee] bg-white px-3 py-2.5 text-sm text-[#202860] placeholder:text-[#8aa0aa] focus:border-[#18a0b8] focus:outline-none focus:ring-2 focus:ring-[#18a0b8]/25";
const authPageClass =
  "flex min-h-screen items-center justify-center bg-[#182048] bg-cover bg-center bg-no-repeat px-4 py-8";
const authPageStyle = {
  backgroundImage: `url(${loginBackground})`,
};
const authCardClass =
  "w-full max-w-lg rounded-2xl border border-[#d8e8ee] border-t-4 border-t-[#18a0b8] bg-white p-6 shadow-[0_24px_60px_rgba(17,23,53,0.35)]";

const RegisterPage = () => {
  const navigate = useNavigate();
  const {
    register: registerUser,
    user,
    loading,
    error,
    clearError,
  } = useAuth();
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [phoneInputValue, setPhoneInputValue] = useState("+1");

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    mode: "onBlur",
    defaultValues: {
      phone: "+1",
    },
  });

  useEffect(() => {
    return () => clearError();
  }, [clearError]);

  useEffect(() => {
    if (!successMessage) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      navigate("/login", { replace: true });
    }, 1200);

    return () => window.clearTimeout(timeoutId);
  }, [successMessage, navigate]);

  const onSubmit = async (values: RegisterFormValues) => {
    const normalizedPhone = values.phone?.trim() ?? "";
    const phoneForSubmission =
      normalizedPhone === "" || normalizedPhone === "+1" ? undefined : normalizedPhone;

    try {
      await registerUser({
        name: values.name,
        email: values.email,
        password: values.password,
        phone: phoneForSubmission,
      });

      setSuccessMessage(
        "Account created successfully. Redirecting to login...",
      );
    } catch (err) {
      setError("root", {
        message: err instanceof Error ? err.message : "Unable to register",
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
            Create Account
          </h1>
          <p className="mt-1 text-sm text-[#58707d]">
            Start your advisor workspace in under a minute.
          </p>
        </div>

        {successMessage && (
          <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            {successMessage}
          </div>
        )}

        {(error || errors.root) && !successMessage && (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {errors.root?.message ?? error}
          </div>
        )}

        <form
          className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2"
          onSubmit={handleSubmit(onSubmit)}
          noValidate
        >
          <div className="sm:col-span-2">
            <label
              className="text-sm font-medium text-[#202860]"
              htmlFor="name"
            >
              Full Name
            </label>
            <input
              id="name"
              type="text"
              className={inputClass}
              {...register("name")}
            />
            {errors.name && (
              <p className="mt-1 text-xs text-red-600">{errors.name.message}</p>
            )}
          </div>

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
            <label
              className="text-sm font-medium text-[#202860]"
              htmlFor="phone"
            >
              Phone
            </label>
            <input
              id="phone"
              type="tel"
              className={inputClass}
              inputMode="numeric"
              autoComplete="tel-national"
              maxLength={12}
              placeholder="+15551234567"
              {...register("phone")}
              value={phoneInputValue}
              onChange={(event) => {
                const nextValue = normalizeUsPhoneInput(event.target.value);
                setPhoneInputValue(nextValue);
                setValue("phone", nextValue, {
                  shouldDirty: true,
                  shouldValidate: true,
                });
              }}
            />
            {errors.phone && (
              <p className="mt-1 text-xs text-red-600">
                {errors.phone.message}
              </p>
            )}
          </div>

          <div>
            <label
              className="text-sm font-medium text-[#202860]"
              htmlFor="password"
            >
              Password
            </label>
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

          <div>
            <label
              className="text-sm font-medium text-[#202860]"
              htmlFor="confirmPassword"
            >
              Confirm Password
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

          <div className="sm:col-span-2">
            <button
              type="submit"
              disabled={isSubmitting || loading || Boolean(successMessage)}
              className="w-full rounded-xl bg-[#202860] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#182048] focus:outline-none focus:ring-2 focus:ring-[#18a0b8]/30 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSubmitting || loading ? "Creating..." : "Create Account"}
            </button>
          </div>
        </form>

        <p className="mt-4 text-sm text-[#58707d]">
          Already have an account?{" "}
          <Link
            className="font-semibold text-[#108da3] hover:text-[#18a0b8]"
            to="/login"
          >
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
};

export default RegisterPage;
