import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "danger";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  loading?: boolean;
  leftIcon?: ReactNode;
}

const cn = (...classes: Array<string | false | null | undefined>): string =>
  classes.filter(Boolean).join(" ");

const variantClasses: Record<ButtonVariant, string> = {
  primary: "bg-[#0a1633] text-white hover:bg-[#0f2149] focus:ring-[#0a1633]/30",
  secondary:
    "border border-[#d9e4f8] bg-white text-[#0a1633] hover:bg-[#f7faff] focus:ring-[#8ea4d8]/30",
  danger: "bg-[#b42318] text-white hover:bg-[#912018] focus:ring-[#b42318]/30",
};

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = "primary",
      loading = false,
      disabled = false,
      className,
      leftIcon,
      children,
      ...props
    },
    ref,
  ) => {
    const isDisabled = disabled || loading;

    return (
      <button
        ref={ref}
        type="button"
        disabled={isDisabled}
        className={cn(
          "inline-flex items-center justify-center gap-2 rounded-full px-4 py-2 text-sm font-semibold transition focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60",
          variantClasses[variant],
          className,
        )}
        {...props}
      >
        {loading ? (
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
        ) : (
          leftIcon
        )}
        {children}
      </button>
    );
  },
);

Button.displayName = "Button";

export default Button;
