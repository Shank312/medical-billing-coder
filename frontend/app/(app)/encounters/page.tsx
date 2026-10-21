"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ApiClientError, api } from "@/lib/api";
import type { Encounter } from "@/lib/types";
import { filterEncounters } from "@/lib/utils";
import type { EncounterFilter } from "@/lib/utils";
import { EncounterTable } from "@/components/coding/EncounterTable";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Input } from "@/components/ui/Input";
import { Skeleton } from "@/components/ui/Skeleton";

const PAGE_SIZE = 25;
const FILTERS = [
  { value: "all", label: "All statuses" },
  { value: "coded", label: "Coded" },
  { value: "pending", label: "Pending review" },
  { value: "not-coded", label: "Not coded" },
] as const;

export default function EncountersPage() {
  const [encounters, setEncounters] = useState<Encounter[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<string>("all");

  const load = useCallback(async (pageOffset: number) => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.listEncounters({ limit: PAGE_SIZE, offset: pageOffset });
      setEncounters(result.items);
      setTotal(result.total);
      setOffset(result.offset);
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Failed to load encounters.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(0);
  }, [load]);

  const filtered = useMemo(
    () => filterEncounters(encounters, search, filter as EncounterFilter),
    [encounters, search, filter],
  );

  const hasPrev = offset > 0;
  const hasNext = offset + encounters.length < total;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Encounters</h1>
          <p className="mt-1 text-sm text-slate-500">
            {total} encounter{total === 1 ? "" : "s"}
          </p>
        </div>
        <Link href="/encounters/new">
          <Button>New encounter</Button>
        </Link>
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="min-w-[240px] flex-1">
          <Input
            id="search"
            label="Search"
            type="search"
            placeholder="Search by patient reference, type, or date"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <div className="w-full sm:w-auto">
          <label htmlFor="filter" className="block text-sm font-medium text-slate-700">
            Status
          </label>
          <select
            id="filter"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500"
          >
            {FILTERS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-12 w-full" />
          ))}
        </div>
      ) : error ? (
        <ErrorState message={error} onRetry={() => load(offset)} />
      ) : filtered.length === 0 ? (
        <EmptyState
          title={encounters.length === 0 ? "No encounters yet" : "No matching encounters"}
          description={
            encounters.length === 0
              ? "Create an encounter to begin the coding workflow."
              : "Try adjusting your search or filter."
          }
          action={
            <Link href="/encounters/new">
              <Button>New encounter</Button>
            </Link>
          }
        />
      ) : (
        <EncounterTable encounters={filtered} />
      )}

      {!loading && !error && total > PAGE_SIZE ? (
        <div className="flex items-center justify-between">
          <Button variant="secondary" disabled={!hasPrev} onClick={() => load(offset - PAGE_SIZE)}>
            Previous
          </Button>
          <span className="text-sm text-slate-500">
            {total === 0 ? 0 : offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
          </span>
          <Button variant="secondary" disabled={!hasNext} onClick={() => load(offset + PAGE_SIZE)}>
            Next
          </Button>
        </div>
      ) : null}
    </div>
  );
}
