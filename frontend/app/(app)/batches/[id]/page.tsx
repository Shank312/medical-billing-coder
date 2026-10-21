"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ApiClientError, api } from "@/lib/api";
import type { BatchDetail, BatchDocument } from "@/lib/types";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/ErrorState";
import { Spinner } from "@/components/ui/Spinner";

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString() : "—";
}

function statusLabel(status: string) {
  switch (status) {
    case "pending":
      return "Queued";
    case "processing":
      return "Processing";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    case "requires_manual":
      return "Needs manual";
    default:
      return status;
  }
}

export default function BatchDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [batch, setBatch] = useState<BatchDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    try {
      setBatch(await api.getBatch(id));
      setError(null);
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to load the batch.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!batch) return;
    const active = batch.documents.some((d) => d.extraction_status === "pending" || d.extraction_status === "processing");
    if (!active) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function poll() {
      try {
        const next = await api.getBatch(id);
        if (cancelled) return;
        setBatch(next);
        const stillActive = next.documents.some(
          (d) => d.extraction_status === "pending" || d.extraction_status === "processing",
        );
        if (stillActive) timer = setTimeout(poll, 2000);
      } catch {
        if (!cancelled) timer = setTimeout(poll, 3000);
      }
    }

    poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [batch, id]);

  async function handleRetry(document: BatchDocument) {
    setBusy(document.id);
    setError(null);
    try {
      await api.retryDocument(id, document.id);
      await load();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Retry failed.");
    } finally {
      setBusy(null);
    }
  }

  async function handleExport() {
    setExporting(true);
    setError(null);
    try {
      await api.exportBatchCsv(id);
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Export failed.");
    } finally {
      setExporting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <Spinner className="h-8 w-8 text-brand-600" />
      </div>
    );
  }
  if (error && !batch) return <ErrorState message={error} onRetry={load} />;
  if (!batch) return null;

  const hasActive = batch.documents.some(
    (d) => d.extraction_status === "pending" || d.extraction_status === "processing",
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Batch</h1>
          <p className="mt-1 text-sm text-slate-500">
            Created {formatDate(batch.created_at)} · Date of service {formatDate(batch.date_of_service)}
          </p>
        </div>
        <div className="text-sm text-slate-600">
          {batch.processed_documents}/{batch.total_documents} processed · {batch.failed_documents} failed
          <div className="mt-2">
            <Button loading={exporting} disabled={exporting} onClick={handleExport}>
              Export CSV
            </Button>
          </div>
        </div>
      </div>

      {hasActive ? (
        <div
          className="flex items-center gap-2 rounded-lg border border-brand-200 bg-brand-50 px-4 py-3 text-sm text-brand-800"
          role="status"
        >
          <Spinner className="h-4 w-4 text-brand-600" />
          Processing documents…
        </div>
      ) : null}

      {error ? <Alert variant="error">{error}</Alert> : null}

      <section className="rounded-xl border border-slate-200 bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">Documents</h2>
        {batch.documents.length === 0 ? (
          <p className="text-sm text-slate-500">No documents in this batch.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-slate-500">
                <tr>
                  <th className="px-3 py-2">File</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Encounter</th>
                  <th className="px-3 py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {batch.documents.map((d) => (
                  <tr key={d.id} className="border-t border-slate-100">
                    <td className="px-3 py-2">
                      <div className="font-medium text-slate-800">{d.original_filename}</div>
                      <div className="text-xs text-slate-400">
                        {d.media_type} · {d.byte_size} bytes
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      <span className="font-medium">{statusLabel(d.extraction_status)}</span>
                      {d.error_code ? (
                        <div className="text-xs text-red-600">{d.error_code}</div>
                      ) : null}
                    </td>
                    <td className="px-3 py-2">
                      {d.encounter_id ? (
                        <Link className="text-brand-700 hover:underline" href={`/encounters/${d.encounter_id}`}>
                          Open workspace
                        </Link>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      {d.extraction_status === "failed" ? (
                        <Button size="sm" loading={busy === d.id} onClick={() => handleRetry(d)}>
                          Retry
                        </Button>
                      ) : null}
                    </td>
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
