import { buildNoteSegments, filterEncounters, formatDate, truncate } from "@/lib/utils";
import type { Encounter } from "@/lib/types";

describe("buildNoteSegments", () => {
  test("splits the note around a highlight", () => {
    const segments = buildNoteSegments("hello world", [{ start: 6, end: 11, suggestionId: "s1" }]);
    expect(segments).toEqual([
      { text: "hello ", highlighted: false },
      { text: "world", highlighted: true, suggestionId: "s1" },
    ]);
  });

  test("ignores out-of-range offsets", () => {
    expect(buildNoteSegments("abc", [{ start: 0, end: 99 }])).toEqual([
      { text: "abc", highlighted: false },
    ]);
  });

  test("ignores negative and inverted offsets", () => {
    expect(
      buildNoteSegments("abc", [
        { start: -1, end: 2 },
        { start: 2, end: 0 },
      ]),
    ).toEqual([{ text: "abc", highlighted: false }]);
  });
});

describe("filterEncounters", () => {
  const encounters: Encounter[] = [
    { id: "e1", patient_reference: "MRN-1", encounter_type: "office visit", date_of_service: "2025-03-15", place_of_service: "11", payer_context: null, status: "draft", created_at: "2025-03-15T00:00:00Z", coding_status: "completed", review_status: "pending" },
    { id: "e2", patient_reference: "MRN-2", encounter_type: "telehealth", date_of_service: "2025-04-01", place_of_service: "02", payer_context: null, status: "draft", created_at: "2025-04-01T00:00:00Z", coding_status: null, review_status: null },
  ];

  test("filters by search on patient reference", () => {
    expect(filterEncounters(encounters, "MRN-1", "all")).toHaveLength(1);
  });

  test("filters by coded status", () => {
    const result = filterEncounters(encounters, "", "coded");
    expect(result).toHaveLength(1);
    expect(result[0].patient_reference).toBe("MRN-1");
  });

  test("filters by not-coded status", () => {
    const result = filterEncounters(encounters, "", "not-coded");
    expect(result).toHaveLength(1);
    expect(result[0].patient_reference).toBe("MRN-2");
  });
});

test("formatDate falls back for invalid input", () => {
  expect(formatDate("not-a-date")).toBe("not-a-date");
});

test("truncate shortens long text with an ellipsis", () => {
  expect(truncate("abcdef", 4)).toBe("abc…");
  expect(truncate("abc", 4)).toBe("abc");
});
