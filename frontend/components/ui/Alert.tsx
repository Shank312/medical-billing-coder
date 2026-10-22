import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type AlertProps = {
  variant?: "error" | "info" | "success" | "warning";
  children: ReactNode;
};

const STYLES: Record<NonNullable<AlertProps["variant"]>, string> = {
  error: "bg-red-50 text-red-800 ring-red-200",
  info: "bg-brand-50 text-brand-800 ring-brand-200",
  success: "bg-emerald-50 text-emerald-800 ring-emerald-200",
  warning: "bg-amber-50 text-amber-800 ring-amber-200",
};

export function Alert({ variant = "error", children }: AlertProps) {
  return (
    <div
      className={cn("rounded-lg px-4 py-3 text-sm ring-1 ring-inset", STYLES[variant])}
      role={variant === "error" ? "alert" : "status"}
    >
      {children}
    </div>
  );
}
