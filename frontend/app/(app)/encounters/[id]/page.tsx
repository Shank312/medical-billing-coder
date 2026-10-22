"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { ApiClientError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { EncounterDetail, ReviewDecisionType } from "@/lib/types";
import { formatDate } from "@/lib/utils";
import { NoteViewer } from "@/components/coding/NoteViewer";
import { SuggestionCard } from "@/components/coding/SuggestionCard";
import { codingStatusInfo, encounterReviewStatusInfo } from "@/components/coding/status";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Spinner } from "@/components/ui/Spinner";

const REVIEW_ROLES = ["owner", "admin", "coder", "biller"];
const WRITE_ROLES = ["owner", "admin", "provider", "coder"];

function MetaItem({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <dt className="text-[11px] font-semibold uppercase tracking-wide text-ink-faint">{label}</dt>
      <dd className="mt-0.5 font-medium text-ink">{value || "—"}</dd>
    </div>
  );
}

function WarningIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.6} aria-hidden="true">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.008v.008H12v-.008Z"
      />
    </svg>
  );
}

function SuggestionGroup({
  title,
  suggestions,
  canReview,
  reviewBusy,
  onSelectEvidence,
  onReview,
}: {
  title: string;
  suggestions: ReturnType<typeof groupSuggestions>["diagnoses"];
  canReview: boolean;
  reviewBusy: string | null;
  onSelectEvidence: (suggestionId: string, start: number, end: number) => void;
  onReview: (suggestionId: string, decision: ReviewDecisionType, correctedCode?: string, note?: string) => Promise<void>;
}) {
  if (suggestions.length === 0) return null;
  return (
    <section aria-label={title}>
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-ink-faint">{title}</h2>
      <div className="space-y-3">
        {suggestions.map((suggestion) => (
          <SuggestionCard
            key={suggestion.id}
            suggestion={suggestion}
            canReview={canReview}
            busy={reviewBusy === suggestion.id}
            onSelectEvidence={onSelectEvidence}
            onReview={(decision, correctedCode, note) =>
              onReview(suggestion.id, decision, correctedCode, note)
            }
          />
        ))}
      </div>
    </section>
  );
}

function groupSuggestions(detail: EncounterDetail | null) {
  const suggestions = detail?.suggestions ?? [];
  return {
    diagnoses: suggestions.filter((s) => s.code_type === "icd10cm"),
    procedures: suggestions.filter((s) => s.code_type === "cpt" || s.code_type === "hcpcs"),
    modifiers: suggestions.filter((s) => s.code_type === "modifier"),
  };
}

export default function EncounterWorkspacePage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const { hasRole } = useAuth();

  const [detail, setDetail] = useState<EncounterDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [reviewBusy, setReviewBusy] = useState<string | null>(null);
  const [activeSuggestion, setActiveSuggestion] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDetail(await api.getEncounter(id));
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to load the encounter.");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!jobId || !polling) return;
    const currentJobId = jobId;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    async function poll() {
      try {
        const job = await api.getCodingJob(currentJobId);
        if (cancelled) return;
        if (job.status === "completed") {
          setPolling(false);
          setNotice("Coding completed.");
          await load();
        } else if (job.status === "failed") {
          setPolling(false);
          setError(job.error_code ? `Coding failed (${job.error_code}).` : "Coding failed.");
        } else {
          timer = setTimeout(poll, 2000);
        }
      } catch {
        if (!cancelled) timer = setTimeout(poll, 3000);
      }
    }

    poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [jobId, polling, load]);

  const canReview = hasRole(...REVIEW_ROLES);
  const canSubmit = hasRole(...WRITE_ROLES);

  const evidenceSpans = useMemo(
    () =>
      (detail?.suggestions ?? []).flatMap((s) =>
        s.evidence.map((ev) => ({ start: ev.start_offset, end: ev.end_offset, suggestionId: s.id })),
      ),
    [detail],
  );

  async function handleSubmitCoding() {
    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const job = await api.submitCoding(id);
      setJobId(job.id);
      setPolling(true);
      setNotice("Coding queued.");
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "The coding request failed.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleReview(
    suggestionId: string,
    decision: ReviewDecisionType,
    correctedCode?: string,
    note?: string,
  ) {
    setReviewBusy(suggestionId);
    setError(null);
    try {
      await api.reviewSuggestion(id, suggestionId, { decision, corrected_code: correctedCode, note });
      await load();
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "The review could not be saved.");
    } finally {
      setReviewBusy(null);
    }
  }

  async function handleExportPdf() {
    setExporting(true);
    setError(null);
    try {
      await api.exportPdfSummary(id);
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "The summary could not be generated.");
    } finally {
      setExporting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Spinner className="h-8 w-8 text-accent-600" />
      </div>
    );
  }

  if (error && !detail) {
    return <ErrorState message={error} onRetry={load} />;
  }

  if (!detail) return null;

  const groups = groupSuggestions(detail);
  const coding = codingStatusInfo(detail.coding_status);
  const review = encounterReviewStatusInfo(detail.review_status);
  const hasSuggestions =
    groups.diagnoses.length > 0 || groups.procedures.length > 0 || groups.modifiers.length > 0;
  const noteLength = detail.note?.length ?? 0;

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight text-ink">Encounter</h1>
            <Badge variant={coding.variant}>{coding.label}</Badge>
            <Badge variant={review.variant}>{review.label}</Badge>
          </div>
          <p className="mt-1 text-sm text-ink-muted">Service date {formatDate(detail.date_of_service)}</p>
          <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-3">
            <MetaItem label="Patient" value={detail.patient_reference} />
            <MetaItem label="Encounter type" value={detail.encounter_type} />
            <MetaItem label="Place of service" value={detail.place_of_service} />
          </dl>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" loading={exporting} disabled={exporting} onClick={handleExportPdf}>
            PDF summary
          </Button>
          {canSubmit ? (
            <Button loading={submitting || polling} disabled={polling} onClick={handleSubmitCoding}>
              {polling
                ? "Coding in progress…"
                : detail.suggestions.length > 0
                  ? "Re-run coding"
                  : "Run coding"}
            </Button>
          ) : null}
        </div>
      </header>

      {error ? <Alert variant="error">{error}</Alert> : null}
      {notice ? <Alert variant="info">{notice}</Alert> : null}
      {polling ? (
        <div
          className="flex items-center gap-2 rounded-xl border border-accent-200 bg-accent-50 px-4 py-3 text-sm text-accent-800"
          role="status"
        >
          <Spinner className="h-4 w-4 text-accent-600" />
          Coding in progress…
        </div>
      ) : null}

      {(detail.missing_documentation.length > 0 || detail.contradictions.length > 0) && (
        <div className="space-y-2">
          {detail.missing_documentation.length > 0 ? (
            <div className="flex gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              <WarningIcon />
              <div>
                <p className="font-semibold">Missing documentation</p>
                <ul className="mt-1 list-inside list-disc space-y-0.5">
                  {detail.missing_documentation.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </div>
          ) : null}
          {detail.contradictions.length > 0 ? (
            <div className="flex gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
              <WarningIcon />
              <div>
                <p className="font-semibold">Contradictions</p>
                <ul className="mt-1 list-inside list-disc space-y-0.5">
                  {detail.contradictions.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </div>
          ) : null}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <section aria-label="Clinical documentation" className="min-w-0">
          <Card className="flex h-full flex-col overflow-hidden">
            <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
              <h2 className="text-sm font-semibold text-ink">Clinical documentation</h2>
              <span className="text-xs text-ink-faint">{noteLength.toLocaleString()} characters</span>
            </div>
            <div className="max-h-[70vh] flex-1 overflow-y-auto p-4">
              <NoteViewer note={detail.note} spans={evidenceSpans} activeSuggestionId={activeSuggestion} />
            </div>
          </Card>
        </section>

        <section aria-label="Coding suggestions" className="min-w-0 space-y-6">
          {!hasSuggestions ? (
            <EmptyState
              title="No coding suggestions yet"
              description={
                canSubmit
                  ? "Run coding to generate candidate suggestions for review."
                  : "No coding suggestions have been generated for this encounter."
              }
            />
          ) : null}

          <SuggestionGroup
            title="Diagnoses"
            suggestions={groups.diagnoses}
            canReview={canReview}
            reviewBusy={reviewBusy}
            onSelectEvidence={(suggestionId) => setActiveSuggestion(suggestionId)}
            onReview={handleReview}
          />
          <SuggestionGroup
            title="Procedures"
            suggestions={groups.procedures}
            canReview={canReview}
            reviewBusy={reviewBusy}
            onSelectEvidence={(suggestionId) => setActiveSuggestion(suggestionId)}
            onReview={handleReview}
          />
          <SuggestionGroup
            title="Modifiers"
            suggestions={groups.modifiers}
            canReview={canReview}
            reviewBusy={reviewBusy}
            onSelectEvidence={(suggestionId) => setActiveSuggestion(suggestionId)}
            onReview={handleReview}
          />
        </section>
      </div>

      {detail.reviews.length > 0 ? (
        <section aria-label="Review history" className="rounded-2xl border border-line bg-white p-4 shadow-card">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-ink-faint">
            Review history
          </h2>
          <ul className="divide-y divide-line">
            {detail.reviews.map((entry) => (
              <li key={entry.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2.5 text-sm">
                <Badge
                  variant={
                    entry.decision === "approved"
                      ? "success"
                      : entry.decision === "rejected"
                        ? "danger"
                        : entry.decision === "corrected"
                          ? "info"
                          : "neutral"
                  }
                >
                  {entry.decision}
                </Badge>
                {entry.corrected_code ? (
                  <span className="font-mono text-ink">{entry.corrected_code}</span>
                ) : null}
                <span className="text-xs text-ink-faint">{formatDate(entry.created_at)}</span>
                {entry.note ? <p className="w-full text-ink-muted">{entry.note}</p> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
