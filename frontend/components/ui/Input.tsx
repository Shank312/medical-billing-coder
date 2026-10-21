import type { InputHTMLAttributes } from "react";

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  id: string;
  error?: string;
};

export function Input({ label, id, error, className = "", ...props }: InputProps) {
  const border = error
    ? "border-red-300 focus:border-red-500 focus:ring-red-500"
    : "border-slate-300 focus:border-brand-500 focus:ring-brand-500";

  return (
    <div className="space-y-1">
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">
        {label}
      </label>
      <input
        id={id}
        className={`block w-full rounded-md border px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 ${border} ${className}`}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        {...props}
      />
      {error ? (
        <p id={`${id}-error`} className="text-sm text-red-600" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
