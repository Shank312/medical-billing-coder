"use client";

import { useState } from "react";
import type { ReviewDecisionType } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";

type Mode = ReviewDecisionType | null;

function IconCheck() {
  return (
    <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2.4} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
    </svg>
  );
}

function IconX() {
  return (
    <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2.4} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
    </svg>
  );
}

function IconEdit() {
  return (
    <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Z" />
    </svg>
  );
}

export function ReviewControls({
  onDecision,
  busy,
}: {
  onDecision: (decision: ReviewDecisionType, correctedCode?: string, note?: string) => Promise<void>;
  busy: boolean;
}) {
  const [mode, setMode] = useState<Mode>(null);
  const [correctedCode, setCorrectedCode] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (mode === null) {
    return (
      <div className="flex flex-wrap gap-2">
        <Button variant="success" size="sm" onClick={() => setMode("approved")}>
          <IconCheck />
          Approve
        </Button>
        <Button variant="danger" size="sm" onClick={() => setMode("rejected")}>
          <IconX />
          Reject
        </Button>
        <Button variant="warning" size="sm" onClick={() => setMode("corrected")}>
          <IconEdit />
          Correct
        </Button>
      </div>
    );
  }

  async function confirm() {
    if (mode === "corrected" && !correctedCode.trim()) {
      setError("A corrected code is required.");
      return;
    }
    setError(null);
    await onDecision(mode as ReviewDecisionType, correctedCode.trim() || undefined, note.trim() || undefined);
    setMode(null);
    setCorrectedCode("");
    setNote("");
  }

  return (
    <div className="space-y-3 rounded-xl border border-line bg-surface p-3">
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full bg-accent-500" aria-hidden="true" />
        <span className="text-sm font-semibold text-ink">
          {mode === "approved" ? "Approve suggestion" : mode === "rejected" ? "Reject suggestion" : "Correct code"}
        </span>
      </div>
      {mode === "corrected" ? (
        <Input
          id="corrected-code"
          label="Corrected code"
          value={correctedCode}
          onChange={(event) => setCorrectedCode(event.target.value)}
          error={error ?? undefined}
          placeholder="e.g. F32.9"
        />
      ) : null}
      <Textarea
        id="review-note"
        label="Review note (optional)"
        rows={2}
        value={note}
        onChange={(event) => setNote(event.target.value)}
        placeholder="Add a reason for this decision"
      />
      <div className="flex gap-2">
        <Button size="sm" loading={busy} onClick={confirm}>
          Confirm
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setMode(null)}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
