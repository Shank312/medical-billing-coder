import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { EncounterForm } from "@/components/coding/EncounterForm";

jest.mock("next/navigation", () => ({
  useRouter: () => ({ replace: jest.fn(), back: jest.fn() }),
}));

jest.mock("@/lib/api", () => ({
  api: { createEncounter: jest.fn() },
  ApiClientError: class extends Error {},
}));

import { api } from "@/lib/api";

test("shows validation errors for an empty submit", async () => {
  render(<EncounterForm />);
  fireEvent.click(screen.getByRole("button", { name: /create encounter/i }));

  expect(await screen.findByText("Date of service is required.")).toBeInTheDocument();
  expect(screen.getByText("A clinical note is required.")).toBeInTheDocument();
});

test("submits a valid form", async () => {
  (api.createEncounter as jest.Mock).mockResolvedValue({ id: "enc1" });
  render(<EncounterForm />);

  fireEvent.change(screen.getByLabelText("Date of service"), { target: { value: "2025-03-15" } });
  fireEvent.change(screen.getByLabelText("Clinical note"), {
    target: { value: "Patient presents with a headache." },
  });
  fireEvent.click(screen.getByRole("button", { name: /create encounter/i }));

  await waitFor(() =>
    expect(api.createEncounter).toHaveBeenCalledWith(
      expect.objectContaining({
        date_of_service: "2025-03-15",
        note: "Patient presents with a headache.",
      }),
    ),
  );
});
