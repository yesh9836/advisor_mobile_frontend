import type { HTMLAttributes, ReactNode } from "react";

interface CardProps extends Omit<HTMLAttributes<HTMLDivElement>, "title"> {
  title?: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
}

const cn = (...classes: Array<string | false | null | undefined>): string =>
  classes.filter(Boolean).join(" ");

const Card = ({
  title,
  subtitle,
  action,
  children,
  className,
  ...props
}: CardProps) => {
  return (
    <section
      className={cn(
        "rounded-3xl border border-[#d9e4f8] bg-white p-5 shadow-[0_2px_10px_rgba(10,34,79,0.06)]",
        className,
      )}
      {...props}
    >
      {(title || subtitle || action) && (
        <header className="mb-4 flex items-start justify-between gap-3">
          <div>
            {title && (
              <h2 className="text-xl font-semibold text-[#0a1633]">{title}</h2>
            )}
            {subtitle && (
              <p className="mt-1 text-sm text-[#4c628a]">{subtitle}</p>
            )}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
};

export default Card;
