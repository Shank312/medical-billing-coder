export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  created_at: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token: string;
  user: User;
  organization: Organization;
}

export interface MeResponse {
  user: User;
  organization: Organization;
  roles: string[];
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    request_id: string | null;
  };
}
