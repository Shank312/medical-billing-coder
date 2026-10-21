"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ApiClientError, api } from "@/lib/api";
import type { Encounter } from "@/lib/types";
import { EncounterTable } from "@/components/coding/EncounterTable";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Input } from "@/components/ui/Input";
import { Skeleton } from "@/components/ui/Skeleton";

const PAGE_SIZE = 25;

const STATUS_OPTIONS = [
  { value: "all", label: "All statuses" },
  { value: "coded", label: "Coded" },
  { value: "pending", label: "Pending review" },
  { value: "not_coded", label: "Not coded" },
] as const;

const SORT_OPTIONS = [
  { value: "created_at", label: "Created" },
  { value: "date_of_service", label: "Date of service" },
  { value: "patient_reference", label: "Patient reference" },
  { value: "encounter_type", label: "Encounter type" },
] as const;

const selectClasses =
  "mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500";

export default function EncountersPage() {
  const [encounters, setEncounters] = useState<Encounter[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [status, setStatus] = useState<string>("all");
  const [sort, setSort] = useState<string>("created_at");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [reloadKey, setReloadKey] = useState(0);
  const [exporting, setExporting] = useState<string | null>(null);

  // Debounce search so we do not issue a request per keystroke.
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const result = await api.listEncounters({
          limit: PAGE_SIZE,
          offset,
          search: debouncedSearch || undefined,
          status,
          sort,
          order,
        });
        if (!cancelled) {
          setEncounters(result.items);
          setTotal(result.total);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiClientError ? err.message : "Failed to load encounters.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [debouncedSearch, status, sort, order, offset, reloadKey]);

  const hasPrev = offset > 0;
  const hasNext = offset + encounters.length < total;

  async function handleExport(format: "csv" | "xlsx") {
    setExporting(format);
    setError(null);
    try {
      const params = { search: debouncedSearch || undefined, status, sort, order };
      if (format === "csv") await api.exportCsv(params);
      else await api.exportXlsx(params);
    } catch (err) {
      setError(err instanceof ApiClientError ? err.message : "Export failed.");
    } finally {
      setExporting(null);
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Encounters</h1>
          <p className="mt-1 text-sm text-slate-500">
            {total} encounter{total === 1 ? "" : "s"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button loading={exporting === "csv"} disabled={exporting !== null} onClick={() => handleExport("csv")}>
            Export CSV
          </Button>
          <Button loading={exporting === "xlsx"} disabled={exporting !== null} onClick={() => handleExport("xlsx")}>
            Export XLSX
          </Button>
          <Link href="/encounters/new">
            <Button>New encounter</Button>
          </Link>
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="min-w-[220px] flex-1">
          <Input
            id="search"
            label="Search"
            type="search"
            placeholder="Search by patient reference or type"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setOffset(0);
            }}
          />
        </div>
        <div className="w-full sm:w-40">
          <label htmlFor="status" className="block text-sm font-medium text-slate-700">
            Status
          </label>
          <select
            id="status"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setOffset(0);
            }}
            className={selectClasses}
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div className="w-full sm:w-44">
          <label htmlFor="sort" className="block text-sm font-medium text-slate-700">
            Sort by
          </label>
          <select
            id="sort"
            value={sort}
            onChange={(event) => {
              setSort(event.target.value);
              setOffset(0);
            }}
            className={selectClasses}
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div className="w-full sm:w-28">
          <label htmlFor="order" className="block text-sm font-medium text-slate-700">
            Order
          </label>
          <select
            id="order"
            value={order}
            onChange={(event) => {
              setOrder(event.target.value as "asc" | "desc");
              setOffset(0);
            }}
            className={selectClasses}
          >
            <option value="desc">Newest</option>
            <option value="asc">Oldest</option>
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
        <ErrorState message={error} onRetry={() => setReloadKey((key) => key + 1)} />
      ) : encounters.length === 0 ? (
        <EmptyState
          title="No encounters"
          description="No encounters match the current search and filters, or none have been created yet."
          action={
            <Link href="/encounters/new">
              <Button>New encounter</Button>
            </Link>
          }
        />
      ) : (
        <EncounterTable encounters={encounters} />
      )}

      {!loading && !error && total > PAGE_SIZE ? (
        <div className="flex items-center justify-between">
          <Button
            variant="secondary"
            disabled={!hasPrev}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            Previous
          </Button>
          <span className="text-sm text-slate-500">
            {total === 0 ? 0 : offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
          </span>
          <Button
            variant="secondary"
            disabled={!hasNext}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            Next
          </Button>
        </div>
      ) : null}
    </div>
  );
}
