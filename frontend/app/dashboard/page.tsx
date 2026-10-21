import Link from "next/link";

export default function DashboardPage() {
  return (
    <main className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
          <span className="text-lg font-semibold text-brand-700">Medical Billing Coder</span>
          <Link href="/login" className="text-sm text-slate-600 hover:text-slate-900">
            Sign out
          </Link>
        </div>
      </header>
      <div className="mx-auto max-w-6xl px-4 py-12">
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-12 text-center">
          <h1 className="text-xl font-semibold text-slate-900">Dashboard</h1>
          <p className="mt-2 text-sm text-slate-500">
            The split-screen coding review workspace arrives in Phase 3.
          </p>
        </div>
      </div>
    </main>
  );
}
