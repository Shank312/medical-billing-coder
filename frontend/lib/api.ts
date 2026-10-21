import type { ApiErrorBody, AuthResponse, MeResponse } from "./types";

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

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    credentials: "include",
  });

  if (!response.ok) {
    let body: ApiErrorBody;
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      body = {
        error: {
          code: "network_error",
          message: `Request failed with status ${response.status}`,
          request_id: null,
        },
      };
    }
    throw new ApiClientError(response.status, body);
  }

  return (await response.json()) as T;
}

export const api = {
  login(email: string, password: string, mfaCode?: string, organizationId?: string) {
    return request<AuthResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email,
        password,
        mfa_code: mfaCode,
        organization_id: organizationId,
      }),
    });
  },

  register(payload: {
    organization_name: string;
    full_name: string;
    email: string;
    password: string;
  }) {
    return request<AuthResponse>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  logout(refreshToken?: string) {
    return request<{ message: string }>("/api/v1/auth/logout", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  },

  me(accessToken: string) {
    return request<MeResponse>("/api/v1/auth/me", {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
  },
};
