import { render, screen } from "@testing-library/react";
import { SuggestionCard } from "@/components/coding/SuggestionCard";
import type { Suggestion } from "@/lib/types";

const baseSuggestion: Suggestion = {
  id: "s1",
  code_type: "icd10cm",
  code: "F32.9",
  description: "Major depressive disorder",
  confidence: 0.9,
  rationale: "documented",
  applies_to: null,
  validation_status: "reference_data_unavailable",
  review_status: "pending",
  corrected_code: null,
  flags: [],
  evidence: [],
};

function renderCard(suggestion: Suggestion) {
  render(
    <SuggestionCard
      suggestion={suggestion}
      canReview={false}
      busy={false}
      onSelectEvidence={jest.fn()}
      onReview={jest.fn()}
    />,
  );
}

test("labels model confidence as uncalibrated", () => {
  renderCard(baseSuggestion);
  expect(screen.getByText(/uncalibrated/i)).toBeInTheDocument();
});

test("shows reference-data-unavailable and does not claim validation", () => {
  renderCard(baseSuggestion);
  expect(screen.getByText("Reference data unavailable")).toBeInTheDocument();
  expect(screen.queryByText("Validated")).not.toBeInTheDocument();
});

test("renders description as plain text (no HTML injection)", () => {
  renderCard({ ...baseSuggestion, description: "<img src=x onerror=alert(1)>" });
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  expect(screen.getByText(/<img/)).toBeInTheDocument();
});
