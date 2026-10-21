"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ApiClientError, api } from "@/lib/api";
import type { Batch } from "@/lib/types";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Input } from "@/components/ui/Input";

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleDateString() : "—";
}

export default function BatchesPage() {
  const [batches, setBatches] = useState<Batch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [date, setDate] = useState("");
  const [creating, setCreating] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [selectedBatch, setSelectedBatch] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.listBatches();
      setBatches(result.items);
      if (result.items.length > 0 && !selectedBatch) setSelectedBatch(result.items[0].id);
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to load batches.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleCreate() {
    setCreating(true);
    setError(null);
    setNotice(null);
    try {
      const batch = await api.createBatch(date || undefined);
      setNotice(`Batch created.`);
      setSelectedBatch(batch.id);
      await load();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Could not create the batch.");
    } finally {
      setCreating(false);
    }
  }

  async function handleUpload() {
    const input = fileInput.current;
    if (!input?.files?.length || !selectedBatch) {
      setError("Choose a batch and at least one file.");
      return;
    }
    setUploading(true);
    setError(null);
    setNotice(null);
    try {
      await api.uploadDocuments(selectedBatch, Array.from(input.files));
      input.value = "";
      setNotice("Upload accepted. Processing started.");
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  if (loading) return <div className="p-6 text-sm text-slate-500">Loading batches…</div>;
  if (error && batches.length === 0) return <ErrorState message={error} onRetry={load} />;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Batch ingestion</h1>
          <p className="mt-1 text-sm text-slate-500">
            Upload clinical PDFs or CSV files for secure, auditable coding.
          </p>
        </div>
      </div>

      {error ? <Alert variant="error">{error}</Alert> : null}
      {notice ? <Alert variant="info">{notice}</Alert> : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">New batch</h2>
          <Input
            id="date_of_service"
            label="Date of service (optional; applies to PDF documents)"
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
          />
          <p className="mt-1 text-xs text-slate-400">CSV rows carry their own date of service.</p>
          <div className="mt-3">
            <Button loading={creating} onClick={handleCreate}>
              Create batch
            </Button>
          </div>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Upload files</h2>
          <label className="mb-1 block text-sm font-medium text-slate-700">Batch</label>
          <select
            className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm"
            value={selectedBatch}
            onChange={(e) => setSelectedBatch(e.target.value)}
          >
            {batches.map((b) => (
              <option key={b.id} value={b.id}>
                {formatDate(b.created_at)} · {b.status}
              </option>
            ))}
          </select>
          <input ref={fileInput} type="file" multiple accept=".pdf,.csv" className="mt-3 block w-full text-sm" />
          <p className="mt-1 text-xs text-slate-400">.pdf or .csv · up to 5 MB per file · 50 files per batch.</p>
          <div className="mt-3">
            <Button loading={uploading} disabled={!selectedBatch} onClick={handleUpload}>
              Upload files
            </Button>
          </div>
        </section>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Batches</h2>
        {batches.length === 0 ? (
          <EmptyState title="No batches yet" description="Create a batch and upload documents to begin." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-slate-500">
                <tr>
                  <th className="px-3 py-2">Created</th>
                  <th className="px-3 py-2">Date of service</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Documents</th>
                  <th className="px-3 py-2">Failed</th>
                </tr>
              </thead>
              <tbody>
                {batches.map((b) => (
                  <tr key={b.id} className="border-t border-slate-100">
                    <td className="px-3 py-2">{formatDate(b.created_at)}</td>
                    <td className="px-3 py-2">{formatDate(b.date_of_service)}</td>
                    <td className="px-3 py-2">
                      <Link className="font-medium text-brand-700 hover:underline" href={`/batches/${b.id}`}>
                        {b.status}
                      </Link>
                    </td>
                    <td className="px-3 py-2">{b.total_documents}</td>
                    <td className="px-3 py-2">{b.failed_documents}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
