"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ApiClientError, api } from "@/lib/api";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";

const NOTE_MAX = 50_000;

export function EncounterForm() {
  const router = useRouter();
  const [date, setDate] = useState("");
  const [encounterType, setEncounterType] = useState("");
  const [placeOfService, setPlaceOfService] = useState("");
  const [patientRef, setPatientRef] = useState("");
  const [payer, setPayer] = useState("");
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  function validate(): Record<string, string> {
    const errors: Record<string, string> = {};
    if (!date) errors.date = "Date of service is required.";
    if (!note.trim()) errors.note = "A clinical note is required.";
    if (note.length > NOTE_MAX) errors.note = `Note must be ${NOTE_MAX.toLocaleString()} characters or fewer.`;
    return errors;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errors = validate();
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setLoading(true);
    setError(null);
    try {
      const encounter = await api.createEncounter({
        date_of_service: date,
        encounter_type: encounterType.trim() || undefined,
        place_of_service: placeOfService.trim() || undefined,
        patient_reference: patientRef.trim() || undefined,
        payer_context: payer.trim() || undefined,
        note,
      });
      router.replace(`/encounters/${encounter.id}`);
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to create the encounter.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card className="mx-auto w-full max-w-2xl p-6 md:p-8">
      <h1 className="text-xl font-semibold text-slate-900">New encounter</h1>
      <p className="mt-1 text-sm text-slate-500">
        Enter the clinical documentation. Coding is only run when you explicitly submit it.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 space-y-5" noValidate>
        {error ? <Alert variant="error">{error}</Alert> : null}

        <div>
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-ink-faint">
            Service details
          </h2>
          <div className="space-y-4">
            <Input
              id="date"
              label="Date of service"
              type="date"
              required
              value={date}
              onChange={(event) => setDate(event.target.value)}
              error={fieldErrors.date}
            />

            <div className="grid gap-4 sm:grid-cols-2">
              <Input
                id="encounter-type"
                label="Encounter type"
                value={encounterType}
                onChange={(event) => setEncounterType(event.target.value)}
                placeholder="e.g. office visit"
              />
              <Input
                id="place-of-service"
                label="Place of service"
                value={placeOfService}
                onChange={(event) => setPlaceOfService(event.target.value)}
                placeholder="e.g. 11"
              />
            </div>
          </div>
        </div>

        <div>
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-ink-faint">
            Patient & billing
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              id="patient-reference"
              label="Patient reference"
              value={patientRef}
              onChange={(event) => setPatientRef(event.target.value)}
              placeholder="Opaque identifier (no names)"
            />
            <Input
              id="payer"
              label="Payer context"
              value={payer}
              onChange={(event) => setPayer(event.target.value)}
              placeholder="e.g. Medicare"
            />
          </div>
        </div>

        <div>
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-ink-faint">
            Clinical note
          </h2>
          <Textarea
            id="note"
            label="Clinical note"
            required
            rows={12}
            maxLength={NOTE_MAX}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            error={fieldErrors.note}
            hint={`${note.length.toLocaleString()} / ${NOTE_MAX.toLocaleString()} characters`}
            placeholder="Paste or type the clinical documentation here."
          />
        </div>

        <div className="flex items-center gap-3 border-t border-line pt-4">
          <Button type="submit" loading={loading}>
            {loading ? "Creating…" : "Create encounter"}
          </Button>
          <Button type="button" variant="ghost" onClick={() => router.back()}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  );
}
