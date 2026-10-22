"use client";

import type { ReviewDecisionType, Suggestion } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/utils";
import { ReviewControls } from "./ReviewControls";
import { suggestionReviewStatusInfo, validationStatusInfo } from "./status";

const CODE_TYPE_LABEL: Record<string, string> = {
  icd10cm: "ICD-10-CM",
  cpt: "CPT",
  hcpcs: "HCPCS",
  modifier: "Modifier",
};

const REVIEW_ACCENT: Record<string, string> = {
  success: "border-l-emerald-500",
  danger: "border-l-red-500",
  warning: "border-l-amber-500",
  info: "border-l-accent-500",
  neutral: "border-l-slate-300",
  muted: "border-l-slate-300",
};

export function SuggestionCard({
  suggestion,
  canReview,
  busy,
  onSelectEvidence,
  onReview,
}: {
  suggestion: Suggestion;
  canReview: boolean;
  busy: boolean;
  onSelectEvidence: (suggestionId: string, start: number, end: number) => void;
  onReview: (decision: ReviewDecisionType, correctedCode?: string, note?: string) => Promise<void>;
}) {
  const validation = validationStatusInfo(suggestion.validation_status);
  const review = suggestionReviewStatusInfo(suggestion.review_status);
  const isModifier = suggestion.code_type === "modifier";
  const hallucinated = suggestion.flags.includes("hallucinated_evidence");

  return (
    <div
      className={cn(
        "rounded-2xl border border-line border-l-4 bg-white p-4 shadow-card",
        REVIEW_ACCENT[review.variant] ?? REVIEW_ACCENT.neutral,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-lg font-semibold leading-none text-brand-800">
              {suggestion.code}
            </span>
            <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
              {CODE_TYPE_LABEL[suggestion.code_type] ?? suggestion.code_type}
            </span>
            {suggestion.applies_to ? (
              <span className="text-xs text-ink-muted">applies to {suggestion.applies_to}</span>
            ) : null}
          </div>
          {suggestion.description ? (
            <p className="mt-1.5 text-sm text-ink">{suggestion.description}</p>
          ) : (
            <p className="mt-1.5 text-sm italic text-ink-faint">No description provided</p>
          )}
        </div>
        <Badge variant={review.variant}>{review.label}</Badge>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <Badge variant={validation.variant}>{validation.label}</Badge>
        {hallucinated ? <Badge variant="warning">Evidence could not be matched</Badge> : null}
      </div>

      {!isModifier && suggestion.validation_status !== "valid" ? (
        <p className="mt-2.5 text-xs text-ink-muted">
          {suggestion.validation_status === "reference_data_unavailable"
            ? "Authoritative reference data is not loaded, so this code has not been validated."
            : "This code has not been deterministically validated against an applicable loaded dataset."}
        </p>
      ) : null}

      {suggestion.confidence !== null && suggestion.confidence !== undefined ? (
        <p className="mt-2 text-xs text-ink-faint">
          Model confidence {suggestion.confidence} (uncalibrated — not a probability)
        </p>
      ) : null}

      {suggestion.evidence.length > 0 ? (
        <div className="mt-3.5">
          <h4 className="text-[11px] font-semibold uppercase tracking-wide text-ink-faint">
            Source evidence
          </h4>
          <ul className="mt-1.5 space-y-1.5">
            {suggestion.evidence.map((span, index) => (
              <li key={index}>
                <button
                  type="button"
                  onClick={() => onSelectEvidence(suggestion.id, span.start_offset, span.end_offset)}
                  className="block w-full rounded-lg border border-line bg-surface px-3 py-2 text-left text-sm text-ink transition-colors hover:border-accent-300 hover:bg-accent-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-600"
                >
                  <span className="text-accent-600" aria-hidden="true">
                    &ldquo;
                  </span>
                  {span.quote}
                  <span className="text-accent-600" aria-hidden="true">
                    &rdquo;
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="mt-3.5 text-xs text-ink-faint">No source evidence was provided for this suggestion.</p>
      )}

      {suggestion.rationale ? (
        <div className="mt-3.5">
          <h4 className="text-[11px] font-semibold uppercase tracking-wide text-ink-faint">
            Model rationale <span className="normal-case">(interpretation, not verified)</span>
          </h4>
          <p className="mt-1 text-sm text-ink-muted">{suggestion.rationale}</p>
        </div>
      ) : null}

      {canReview ? (
        <div className="mt-4 border-t border-line pt-3.5">
          <ReviewControls busy={busy} onDecision={onReview} />
        </div>
      ) : null}
    </div>
  );
}
