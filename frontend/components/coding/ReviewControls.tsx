"use client";

import { useState } from "react";
import type { ReviewDecisionType } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";

type Mode = ReviewDecisionType | null;

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
        <Button variant="secondary" size="sm" onClick={() => setMode("approved")}>
          Approve
        </Button>
        <Button variant="secondary" size="sm" onClick={() => setMode("rejected")}>
          Reject
        </Button>
        <Button variant="ghost" size="sm" onClick={() => setMode("corrected")}>
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
    <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
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
          Confirm {mode}
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setMode(null)}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
