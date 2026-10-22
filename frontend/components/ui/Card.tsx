import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Card({ className = "", children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cn("rounded-2xl border border-line bg-white shadow-card", className)}>
      {children}
    </div>
  );
}
