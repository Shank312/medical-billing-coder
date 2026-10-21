import type { Encounter } from "./types";

export function cn(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

export function formatDate(iso: string): string {
  const value = new Date(iso);
  if (Number.isNaN(value.getTime())) return iso;
  return value.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

export interface HighlightSpan {
  start: number;
  end: number;
  suggestionId?: string;
}

export interface NoteSegment {
  text: string;
  highlighted: boolean;
  suggestionId?: string;
}

/**
 * Split a note into segments so that valid evidence offsets can be highlighted.
 * Invalid/out-of-range offsets are silently ignored so they can never crash the
 * page; callers can detect they were dropped by comparing output length.
 */
export function buildNoteSegments(note: string, spans: HighlightSpan[]): NoteSegment[] {
  if (!note) return [];
  const valid = spans
    .filter((s) => s.start >= 0 && s.end <= note.length && s.start < s.end)
    .sort((a, b) => a.start - b.start);

  const segments: NoteSegment[] = [];
  let cursor = 0;
  for (const span of valid) {
    if (span.start < cursor) continue; // skip overlaps
    if (span.start > cursor) {
      segments.push({ text: note.slice(cursor, span.start), highlighted: false });
    }
    segments.push({
      text: note.slice(span.start, span.end),
      highlighted: true,
      suggestionId: span.suggestionId,
    });
    cursor = span.end;
  }
  if (cursor < note.length) {
    segments.push({ text: note.slice(cursor), highlighted: false });
  }
  return segments;
}

export function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

export type EncounterFilter = "all" | "coded" | "pending" | "not-coded";

export function filterEncounters(
  encounters: Encounter[],
  search: string,
  filter: EncounterFilter,
): Encounter[] {
  const query = search.trim().toLowerCase();
  return encounters.filter((encounter) => {
    const matchesSearch =
      !query ||
      (encounter.patient_reference ?? "").toLowerCase().includes(query) ||
      (encounter.encounter_type ?? "").toLowerCase().includes(query) ||
      encounter.date_of_service.includes(query);
    const matchesFilter =
      filter === "all" ||
      (filter === "coded" && encounter.coding_status === "completed") ||
      (filter === "pending" && encounter.review_status === "pending") ||
      (filter === "not-coded" && !encounter.coding_status);
    return matchesSearch && matchesFilter;
  });
}
