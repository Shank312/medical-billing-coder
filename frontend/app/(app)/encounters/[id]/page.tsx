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
import { ErrorState } from "@/components/ui/ErrorState";
import { Spinner } from "@/components/ui/Spinner";

const REVIEW_ROLES = ["owner", "admin", "coder", "biller"];
const WRITE_ROLES = ["owner", "admin", "provider", "coder"];

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
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">{title}</h2>
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
        <Spinner className="h-8 w-8 text-brand-600" />
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

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">
            Encounter · {formatDate(detail.date_of_service)}
          </h1>
          <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-500">
            {detail.encounter_type ? <span>Type: {detail.encounter_type}</span> : null}
            {detail.patient_reference ? <span>Patient: {detail.patient_reference}</span> : null}
            {detail.place_of_service ? <span>POS: {detail.place_of_service}</span> : null}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={coding.variant}>{coding.label}</Badge>
          <Badge variant={review.variant}>{review.label}</Badge>
          <Button loading={exporting} disabled={exporting} onClick={handleExportPdf}>
            PDF summary
          </Button>
          {canSubmit ? (
            <Button loading={submitting || polling} disabled={polling} onClick={handleSubmitCoding}>
              {polling ? "Coding in progress…" : detail.suggestions.length > 0 ? "Re-run coding" : "Run coding"}
            </Button>
          ) : null}
        </div>
      </div>

      {error ? <Alert variant="error">{error}</Alert> : null}
      {notice ? <Alert variant="info">{notice}</Alert> : null}
      {polling ? (
        <div
          className="flex items-center gap-2 rounded-lg border border-brand-200 bg-brand-50 px-4 py-3 text-sm text-brand-800"
          role="status"
        >
          <Spinner className="h-4 w-4 text-brand-600" />
          Coding in progress…
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <section aria-label="Clinical documentation" className="min-w-0">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
              Clinical documentation
            </h2>
            <NoteViewer note={detail.note} spans={evidenceSpans} activeSuggestionId={activeSuggestion} />
          </div>
        </section>

        <section aria-label="Coding suggestions" className="min-w-0 space-y-4">
          {detail.missing_documentation.length > 0 ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              <strong className="font-semibold">Missing documentation:</strong>
              <ul className="mt-1 list-inside list-disc space-y-0.5">
                {detail.missing_documentation.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {detail.contradictions.length > 0 ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
              <strong className="font-semibold">Contradictions:</strong>
              <ul className="mt-1 list-inside list-disc space-y-0.5">
                {detail.contradictions.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {groups.diagnoses.length === 0 &&
          groups.procedures.length === 0 &&
          groups.modifiers.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-500">
              No coding suggestions yet.
              {canSubmit ? " Run coding to generate candidate suggestions." : ""}
            </div>
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
        <section aria-label="Review history" className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Review history
          </h2>
          <ul className="space-y-2">
            {detail.reviews.map((entry) => (
              <li key={entry.id} className="text-sm text-slate-600">
                <Badge variant="neutral">{entry.decision}</Badge>
                {entry.corrected_code ? <span className="ml-2 font-mono">{entry.corrected_code}</span> : null}
                <span className="ml-2 text-slate-400">{formatDate(entry.created_at)}</span>
                {entry.note ? <p className="mt-1 text-slate-500">{entry.note}</p> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
