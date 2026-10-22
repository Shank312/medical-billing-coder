import type { InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  id: string;
  error?: string;
  hint?: string;
};

export function Input({ label, id, error, hint, className = "", ...props }: InputProps) {
  const border = error
    ? "border-red-300 focus:border-red-500 focus:ring-red-500/20"
    : "border-line focus:border-accent-500 focus:ring-accent-500/20";

  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium text-ink">
        {label}
      </label>
      <input
        id={id}
        className={cn(
          "block w-full rounded-lg border bg-white px-3 py-2 text-sm text-ink shadow-sm placeholder:text-ink-faint focus:outline-none focus:ring-2",
          border,
          className,
        )}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
        {...props}
      />
      {hint ? (
        <p id={`${id}-hint`} className="text-xs text-ink-muted">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={`${id}-error`} className="text-sm text-red-700" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
