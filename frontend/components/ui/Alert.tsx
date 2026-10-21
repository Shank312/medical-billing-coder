import type { ReactNode } from "react";

type AlertProps = {
  variant?: "error" | "info";
  children: ReactNode;
};

const STYLES: Record<NonNullable<AlertProps["variant"]>, string> = {
  error: "bg-red-50 text-red-700 ring-red-200",
  info: "bg-blue-50 text-blue-700 ring-blue-200",
};

export function Alert({ variant = "error", children }: AlertProps) {
  return (
    <div
      className={`rounded-md px-4 py-3 text-sm ring-1 ${STYLES[variant]}`}
      role={variant === "error" ? "alert" : "status"}
    >
      {children}
    </div>
  );
}
