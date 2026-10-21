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
        "rounded-lg border bg-white p-4 shadow-card",
        review.variant === "success" ? "border-emerald-200" : "border-slate-200",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-mono text-base font-semibold text-slate-900">{suggestion.code}</span>
            <Badge variant="neutral">{CODE_TYPE_LABEL[suggestion.code_type] ?? suggestion.code_type}</Badge>
            {suggestion.applies_to ? (
              <span className="text-xs text-slate-500">applies to {suggestion.applies_to}</span>
            ) : null}
          </div>
          {suggestion.description ? (
            <p className="mt-1 text-sm text-slate-700">{suggestion.description}</p>
          ) : (
            <p className="mt-1 text-sm italic text-slate-400">No description provided</p>
          )}
        </div>
        <Badge variant={review.variant}>{review.label}</Badge>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        <Badge variant={validation.variant}>{validation.label}</Badge>
        {hallucinated ? <Badge variant="warning">Evidence could not be matched</Badge> : null}
      </div>

      {!isModifier && suggestion.validation_status !== "valid" ? (
        <p className="mt-2 text-xs text-slate-500">
          {suggestion.validation_status === "reference_data_unavailable"
            ? "Authoritative reference data is not loaded, so this code has not been validated."
            : "This code has not been deterministically validated against an applicable loaded dataset."}
        </p>
      ) : null}

      {suggestion.confidence !== null && suggestion.confidence !== undefined ? (
        <p className="mt-2 text-xs text-slate-500">
          Model confidence {suggestion.confidence} (uncalibrated — not a probability)
        </p>
      ) : null}

      {suggestion.evidence.length > 0 ? (
        <div className="mt-3">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Source evidence
          </h4>
          <ul className="mt-1.5 space-y-1.5">
            {suggestion.evidence.map((span, index) => (
              <li key={index}>
                <button
                  type="button"
                  onClick={() => onSelectEvidence(suggestion.id, span.start_offset, span.end_offset)}
                  className="block w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-left text-sm text-slate-700 transition-colors hover:border-brand-300 hover:bg-brand-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500"
                >
                  &ldquo;{span.quote}&rdquo;
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="mt-3 text-xs text-slate-400">No source evidence was provided for this suggestion.</p>
      )}

      {suggestion.rationale ? (
        <div className="mt-3">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Model rationale (interpretation, not verified)
          </h4>
          <p className="mt-1 text-sm text-slate-600">{suggestion.rationale}</p>
        </div>
      ) : null}

      {canReview ? (
        <div className="mt-4 border-t border-slate-100 pt-3">
          <ReviewControls busy={busy} onDecision={onReview} />
        </div>
      ) : null}
    </div>
  );
}
