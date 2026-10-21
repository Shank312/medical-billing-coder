import type {
  ApiErrorBody,
  AuthResponse,
  Batch,
  BatchDetail,
  BatchDocument,
  BatchList,
  CodingJobDetail,
  Encounter,
  EncounterDetail,
  EncounterList,
  MeResponse,
  ReviewDecisionType,
  Suggestion,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiClientError extends Error {
  status: number;
  code: string;

  constructor(status: number, body: ApiErrorBody) {
    super(body.error.message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = body.error.code;
  }
}

let accessToken: string | null = null;
let onAuthExpired: (() => void) | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function setAuthExpiredHandler(handler: () => void) {
  onAuthExpired = handler;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  auth?: boolean;
  headers?: Record<string, string>;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = false, headers: extraHeaders } = options;
  const headers: Record<string, string> = { ...(extraHeaders ?? {}) };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth && accessToken) headers["Authorization"] = `Bearer ${accessToken}`;

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    credentials: "include",
  });

  if (response.status === 401 && auth) {
    onAuthExpired?.();
    throw new ApiClientError(401, {
      error: { code: "unauthorized", message: "Your session has expired.", request_id: null },
    });
  }

  if (!response.ok) {
    let payload: ApiErrorBody;
    try {
      payload = (await response.json()) as ApiErrorBody;
    } catch {
      payload = {
        error: {
          code: "network_error",
          message: `Request failed with status ${response.status}`,
          request_id: null,
        },
      };
    }
    throw new ApiClientError(response.status, payload);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

async function downloadFile(path: string, filename: string): Promise<void> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    credentials: "include",
  });
  if (response.status === 401) {
    onAuthExpired?.();
    throw new ApiClientError(401, {
      error: { code: "unauthorized", message: "Your session has expired.", request_id: null },
    });
  }
  if (!response.ok) {
    let payload: ApiErrorBody;
    try {
      payload = (await response.json()) as ApiErrorBody;
    } catch {
      payload = {
        error: { code: "network_error", message: `Export failed with status ${response.status}`, request_id: null },
      };
    }
    throw new ApiClientError(response.status, payload);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function exportQuery(params: { search?: string; status?: string; sort?: string; order?: "asc" | "desc" }) {
  const query = new URLSearchParams();
  if (params.search) query.set("search", params.search);
  if (params.status && params.status !== "all") query.set("status", params.status);
  if (params.sort && params.sort !== "created_at") query.set("sort", params.sort);
  if (params.order && params.order !== "desc") query.set("order", params.order);
  return query.toString();
}

export const api = {
  // --- auth ---
  login(email: string, password: string, mfaCode?: string, organizationId?: string) {
    return request<AuthResponse>("/api/v1/auth/login", {
      method: "POST",
      body: { email, password, mfa_code: mfaCode, organization_id: organizationId },
    });
  },

  register(payload: { organization_name: string; full_name: string; email: string; password: string }) {
    return request<AuthResponse>("/api/v1/auth/register", { method: "POST", body: payload });
  },

  refresh() {
    return request<AuthResponse>("/api/v1/auth/refresh", { method: "POST", body: {} });
  },

  logout() {
    return request<{ message: string }>("/api/v1/auth/logout", { method: "POST", body: {} });
  },

  me() {
    return request<MeResponse>("/api/v1/auth/me", { auth: true });
  },

  // --- encounters ---
  listEncounters(
    params: {
      limit?: number;
      offset?: number;
      search?: string;
      status?: string;
      sort?: string;
      order?: "asc" | "desc";
    } = {},
  ) {
    const query = new URLSearchParams();
    if (params.limit !== undefined) query.set("limit", String(params.limit));
    if (params.offset !== undefined) query.set("offset", String(params.offset));
    if (params.search) query.set("search", params.search);
    if (params.status && params.status !== "all") query.set("status", params.status);
    if (params.sort && params.sort !== "created_at") query.set("sort", params.sort);
    if (params.order && params.order !== "desc") query.set("order", params.order);
    const qs = query.toString();
    return request<EncounterList>(`/api/v1/encounters${qs ? `?${qs}` : ""}`, { auth: true });
  },

  getEncounter(id: string) {
    return request<EncounterDetail>(`/api/v1/encounters/${id}`, { auth: true });
  },

  createEncounter(payload: {
    date_of_service: string;
    encounter_type?: string;
    place_of_service?: string;
    patient_reference?: string;
    payer_context?: string;
    note: string;
  }) {
    return request<Encounter>("/api/v1/encounters", { method: "POST", body: payload, auth: true });
  },

  submitCoding(encounterId: string, idempotencyKey?: string) {
    const headers: Record<string, string> = {};
    if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
    return request<CodingJobDetail>(`/api/v1/encounters/${encounterId}/code`, {
      method: "POST",
      body: {},
      auth: true,
      headers,
    });
  },

  getCodingJob(jobId: string) {
    return request<CodingJobDetail>(`/api/v1/coding-jobs/${jobId}`, { auth: true });
  },

  reviewSuggestion(
    encounterId: string,
    suggestionId: string,
    payload: { decision: ReviewDecisionType; corrected_code?: string; note?: string },
  ) {
    return request<Suggestion>(
      `/api/v1/encounters/${encounterId}/suggestions/${suggestionId}/review`,
      { method: "POST", body: payload, auth: true },
    );
  },

  // --- batch ingestion ---
  listBatches() {
    return request<BatchList>("/api/v1/batches", { auth: true });
  },

  createBatch(dateOfService?: string) {
    return request<Batch>("/api/v1/batches", {
      method: "POST",
      body: { date_of_service: dateOfService ?? null },
      auth: true,
    });
  },

  getBatch(batchId: string) {
    return request<BatchDetail>(`/api/v1/batches/${batchId}`, { auth: true });
  },

  async uploadDocuments(batchId: string, files: File[]): Promise<BatchDocument[]> {
    const form = new FormData();
    for (const file of files) form.append("files", file);
    const response = await fetch(`${API_BASE}/api/v1/batches/${batchId}/documents`, {
      method: "POST",
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
      body: form,
      credentials: "include",
    });
    if (response.status === 401) {
      onAuthExpired?.();
      throw new ApiClientError(401, {
        error: { code: "unauthorized", message: "Your session has expired.", request_id: null },
      });
    }
    if (!response.ok) {
      let payload: ApiErrorBody;
      try {
        payload = (await response.json()) as ApiErrorBody;
      } catch {
        payload = {
          error: { code: "network_error", message: `Upload failed with status ${response.status}`, request_id: null },
        };
      }
      throw new ApiClientError(response.status, payload);
    }
    return (await response.json()) as BatchDocument[];
  },

  retryDocument(batchId: string, documentId: string) {
    return request<BatchDocument>(`/api/v1/batches/${batchId}/documents/${documentId}/retry`, {
      method: "POST",
      body: {},
      auth: true,
    });
  },

  // --- exports ---
  exportCsv(params: { search?: string; status?: string; sort?: string; order?: "asc" | "desc" } = {}) {
    const qs = exportQuery(params);
    return downloadFile(`/api/v1/encounters/export.csv${qs ? `?${qs}` : ""}`, "coding_export.csv");
  },

  exportXlsx(params: { search?: string; status?: string; sort?: string; order?: "asc" | "desc" } = {}) {
    const qs = exportQuery(params);
    return downloadFile(`/api/v1/encounters/export.xlsx${qs ? `?${qs}` : ""}`, "coding_export.xlsx");
  },

  exportPdfSummary(encounterId: string) {
    return downloadFile(`/api/v1/encounters/${encounterId}/summary.pdf`, `summary_${encounterId}.pdf`);
  },

  exportBatchCsv(batchId: string) {
    return downloadFile(`/api/v1/batches/${batchId}/export.csv`, `batch_${batchId}_export.csv`);
  },
};
