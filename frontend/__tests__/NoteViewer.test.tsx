import { render, screen } from "@testing-library/react";
import { NoteViewer } from "@/components/coding/NoteViewer";

test("renders an unavailable state for a null note", () => {
  render(<NoteViewer note={null} spans={[]} activeSuggestionId={null} />);
  expect(screen.getByText("Source note unavailable.")).toBeInTheDocument();
});

test("renders note text and highlights valid spans", () => {
  const { container } = render(
    <NoteViewer note="hello world" spans={[{ start: 6, end: 11, suggestionId: "s1" }]} activeSuggestionId={null} />,
  );
  const highlighted = container.querySelector("span.bg-amber-100");
  expect(highlighted).toBeInTheDocument();
  expect(highlighted?.textContent).toBe("world");
});

test("does not crash on invalid evidence offsets", () => {
  render(<NoteViewer note="abc" spans={[{ start: 0, end: 99 }]} activeSuggestionId={null} />);
  expect(screen.getByText("abc")).toBeInTheDocument();
});
