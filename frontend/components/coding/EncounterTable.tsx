import Link from "next/link";
import type { Encounter } from "@/lib/types";
import { formatDate } from "@/lib/utils";
import { Badge } from "@/components/ui/Badge";
import { codingStatusInfo, encounterReviewStatusInfo } from "./status";

export function EncounterTable({ encounters }: { encounters: Encounter[] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th scope="col" className="px-4 py-3 font-medium">Date</th>
            <th scope="col" className="px-4 py-3 font-medium">Patient</th>
            <th scope="col" className="px-4 py-3 font-medium">Type</th>
            <th scope="col" className="px-4 py-3 font-medium">Coding</th>
            <th scope="col" className="px-4 py-3 font-medium">Review</th>
            <th scope="col" className="px-4 py-3 font-medium">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {encounters.map((encounter) => {
            const coding = codingStatusInfo(encounter.coding_status);
            const review = encounterReviewStatusInfo(encounter.review_status);
            return (
              <tr key={encounter.id} className="transition-colors hover:bg-slate-50">
                <td className="px-4 py-3 font-medium text-slate-900">
                  {formatDate(encounter.date_of_service)}
                </td>
                <td className="px-4 py-3 text-slate-600">{encounter.patient_reference ?? "—"}</td>
                <td className="px-4 py-3 text-slate-600">{encounter.encounter_type ?? "—"}</td>
                <td className="px-4 py-3">
                  <Badge variant={coding.variant}>{coding.label}</Badge>
                </td>
                <td className="px-4 py-3">
                  <Badge variant={review.variant}>{review.label}</Badge>
                </td>
                <td className="px-4 py-3 text-right">
                  <Link
                    href={`/encounters/${encounter.id}`}
                    className="rounded-md px-2 py-1 text-sm font-medium text-brand-700 transition-colors hover:bg-brand-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500"
                  >
                    Open
                    <span aria-hidden="true"> →</span>
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
