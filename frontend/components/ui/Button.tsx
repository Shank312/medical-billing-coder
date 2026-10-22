import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "success" | "danger" | "warning";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
};

const VARIANT_CLASSES: Record<NonNullable<ButtonProps["variant"]>, string> = {
  primary:
    "bg-brand-700 text-white shadow-sm hover:bg-brand-800 focus-visible:outline-brand-700",
  secondary:
    "bg-white text-ink ring-1 ring-inset ring-line hover:bg-surface focus-visible:outline-brand-700",
  ghost: "text-ink-muted hover:bg-slate-100 hover:text-ink focus-visible:outline-brand-700",
  success:
    "bg-emerald-50 text-emerald-800 ring-1 ring-inset ring-emerald-200 hover:bg-emerald-100 focus-visible:outline-emerald-600",
  danger:
    "bg-red-50 text-red-800 ring-1 ring-inset ring-red-200 hover:bg-red-100 focus-visible:outline-red-600",
  warning:
    "bg-amber-50 text-amber-800 ring-1 ring-inset ring-amber-200 hover:bg-amber-100 focus-visible:outline-amber-600",
};

const SIZE_CLASSES: Record<NonNullable<ButtonProps["size"]>, string> = {
  sm: "px-2.5 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
  lg: "px-5 py-2.5 text-sm",
};

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  className = "",
  children,
  disabled,
  ...props
}: ButtonProps) {
  const base =
    "inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-60";

  return (
    <button
      className={cn(base, VARIANT_CLASSES[variant], SIZE_CLASSES[size], className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading ? (
        <span
          className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-current border-t-transparent"
          aria-hidden="true"
        />
      ) : null}
      {children}
    </button>
  );
}
