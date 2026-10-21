import { buildNoteSegments, formatDate, truncate } from "@/lib/utils";

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

test("formatDate falls back for invalid input", () => {
  expect(formatDate("not-a-date")).toBe("not-a-date");
});

test("truncate shortens long text with an ellipsis", () => {
  expect(truncate("abcdef", 4)).toBe("abc…");
  expect(truncate("abc", 4)).toBe("abc");
});
