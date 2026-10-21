import type { BadgeVariant } from "@/components/ui/Badge";

export interface StatusInfo {
  label: string;
  variant: BadgeVariant;
}

export function codingStatusInfo(status: string | null | undefined): StatusInfo {
  switch (status) {
    case "completed":
      return { label: "Coded", variant: "success" };
    case "failed":
      return { label: "Coding failed", variant: "danger" };
    case "queued":
    case "running":
      return { label: "In progress", variant: "info" };
    case null:
    case undefined:
      return { label: "Not coded", variant: "muted" };
    default:
      return { label: status, variant: "neutral" };
  }
}

export function encounterReviewStatusInfo(status: string | null | undefined): StatusInfo {
  switch (status) {
    case "pending":
      return { label: "Pending review", variant: "warning" };
    case "reviewed":
      return { label: "Reviewed", variant: "success" };
    case null:
    case undefined:
      return { label: "No suggestions", variant: "muted" };
    default:
      return { label: status, variant: "neutral" };
  }
}

export function suggestionReviewStatusInfo(status: string): StatusInfo {
  switch (status) {
    case "approved":
      return { label: "Approved", variant: "success" };
    case "rejected":
      return { label: "Rejected", variant: "danger" };
    case "corrected":
      return { label: "Corrected", variant: "info" };
    case "pending":
      return { label: "Pending", variant: "warning" };
    default:
      return { label: status, variant: "neutral" };
  }
}

export function validationStatusInfo(status: string | null | undefined): StatusInfo {
  switch (status) {
    case "valid":
      return { label: "Validated", variant: "success" };
    case "date_invalid":
      return { label: "Invalid for date of service", variant: "danger" };
    case "unknown":
      return { label: "Not in loaded dataset", variant: "warning" };
    case "reference_data_unavailable":
      return { label: "Reference data unavailable", variant: "muted" };
    case null:
    case undefined:
      return { label: "Not validated", variant: "muted" };
    default:
      return { label: status, variant: "neutral" };
  }
}
