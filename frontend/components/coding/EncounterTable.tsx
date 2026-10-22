import Link from "next/link";
import type { Encounter } from "@/lib/types";
import { formatDate } from "@/lib/utils";
import { Badge } from "@/components/ui/Badge";
import { codingStatusInfo, encounterReviewStatusInfo } from "./status";

export function EncounterTable({ encounters }: { encounters: Encounter[] }) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-line bg-white shadow-card">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead className="border-b border-line bg-surface/60 text-[11px] uppercase tracking-wider text-ink-faint">
          <tr>
            <th scope="col" className="px-4 py-3 font-semibold">Service date</th>
            <th scope="col" className="px-4 py-3 font-semibold">Patient</th>
            <th scope="col" className="px-4 py-3 font-semibold">Type</th>
            <th scope="col" className="px-4 py-3 font-semibold">Coding</th>
            <th scope="col" className="px-4 py-3 font-semibold">Review</th>
            <th scope="col" className="px-4 py-3 font-semibold">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line/70">
          {encounters.map((encounter) => {
            const coding = codingStatusInfo(encounter.coding_status);
            const review = encounterReviewStatusInfo(encounter.review_status);
            return (
              <tr key={encounter.id} className="transition-colors hover:bg-surface/70">
                <td className="px-4 py-3 font-medium text-ink">
                  {formatDate(encounter.date_of_service)}
                </td>
                <td className="px-4 py-3 text-ink-muted">{encounter.patient_reference ?? "—"}</td>
                <td className="px-4 py-3 text-ink-muted">{encounter.encounter_type ?? "—"}</td>
                <td className="px-4 py-3">
                  <Badge variant={coding.variant}>{coding.label}</Badge>
                </td>
                <td className="px-4 py-3">
                  <Badge variant={review.variant}>{review.label}</Badge>
                </td>
                <td className="px-4 py-3 text-right">
                  <Link
                    href={`/encounters/${encounter.id}`}
                    className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm font-medium text-accent-700 transition-colors hover:bg-accent-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-600"
                  >
                    Review
                    <span aria-hidden="true">→</span>
                  </Link>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
