"use client";

import { useEffect, useMemo, useRef } from "react";
import type { HighlightSpan } from "@/lib/utils";
import { buildNoteSegments } from "@/lib/utils";
import { cn } from "@/lib/utils";

export function NoteViewer({
  note,
  spans,
  activeSuggestionId,
}: {
  note: string | null;
  spans: HighlightSpan[];
  activeSuggestionId: string | null;
}) {
  const activeRef = useRef<HTMLSpanElement | null>(null);

  const segments = useMemo(() => buildNoteSegments(note ?? "", spans), [note, spans]);

  useEffect(() => {
    if (activeSuggestionId) {
      activeRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [activeSuggestionId]);

  if (note === null || note === undefined) {
    return (
      <div className="rounded-lg border border-line bg-surface px-4 py-8 text-center text-sm text-ink-muted">
        Source note unavailable.
      </div>
    );
  }

  if (note.length === 0) {
    return (
      <div className="rounded-lg border border-line bg-surface px-4 py-8 text-center text-sm text-ink-muted">
        No source note text.
      </div>
    );
  }

  return (
    <div className="whitespace-pre-wrap break-words font-mono text-[13px] leading-relaxed text-ink">
      {segments.map((segment, index) => {
        const isActive = segment.highlighted && segment.suggestionId === activeSuggestionId;
        return (
          <span
            key={index}
            ref={isActive ? activeRef : undefined}
            className={cn(
              segment.highlighted && "rounded-sm bg-amber-100 px-px",
              isActive && "bg-amber-200 ring-1 ring-amber-400",
            )}
          >
            {segment.text}
          </span>
        );
      })}
    </div>
  );
}
