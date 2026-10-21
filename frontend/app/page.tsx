import Link from "next/link";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-4 text-center">
      <span className="rounded-full bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700">
        Phase 1 · Secure platform core
      </span>
      <h1 className="mt-4 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
        Medical Billing Coder
      </h1>
      <p className="mt-3 max-w-md text-slate-500">
        Secure, evidence-linked medical coding review for US practices and billing teams.
      </p>
      <Link
        href="/login"
        className="mt-8 inline-flex items-center justify-center rounded-md bg-brand-600 px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-brand-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600"
      >
        Sign in
      </Link>
    </main>
  );
}
