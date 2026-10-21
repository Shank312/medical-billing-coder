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

// --- Coding domain (Phase 2/3) ---

export interface Encounter {
  id: string;
  date_of_service: string;
  encounter_type: string | null;
  place_of_service: string | null;
  patient_reference: string | null;
  payer_context: string | null;
  status: string;
  created_at: string;
  coding_status: string | null;
  review_status: string | null;
}

export interface EncounterList {
  items: Encounter[];
  total: number;
  limit: number;
  offset: number;
}

export interface EvidenceSpan {
  quote: string;
  start_offset: number;
  end_offset: number;
}

export interface Suggestion {
  id: string;
  code_type: string;
  code: string;
  description: string | null;
  confidence: number | null;
  rationale: string | null;
  applies_to: string | null;
  validation_status: string | null;
  review_status: string;
  corrected_code: string | null;
  flags: string[];
  evidence: EvidenceSpan[];
}

export interface CodingJob {
  id: string;
  encounter_id: string;
  status: string;
  error_code: string | null;
  code_set_version: string | null;
  schema_version: string | null;
  prompt_version: string | null;
  created_at: string;
  completed_at: string | null;
  missing_documentation: string[];
  contradictions: string[];
}

export interface CodingJobDetail extends CodingJob {
  suggestions: Suggestion[];
}

export interface ReviewDecision {
  id: string;
  decision: string;
  corrected_code: string | null;
  note: string | null;
  created_at: string;
}

export interface EncounterDetail extends Encounter {
  note: string | null;
  missing_documentation: string[];
  contradictions: string[];
  suggestions: Suggestion[];
  reviews: ReviewDecision[];
}

export type ReviewDecisionType = "approved" | "rejected" | "corrected";

// --- Batch ingestion (Phase 5) ---

export interface BatchDocument {
  id: string;
  batch_id: string;
  original_filename: string;
  media_type: string;
  byte_size: number;
  extraction_status: string;
  error_code: string | null;
  encounter_id: string | null;
  coding_job_id: string | null;
  attempt_count: number;
  created_at: string;
  completed_at: string | null;
}

export interface Batch {
  id: string;
  status: string;
  date_of_service: string | null;
  total_documents: number;
  processed_documents: number;
  failed_documents: number;
  created_at: string;
  completed_at: string | null;
}

export interface BatchDetail extends Batch {
  documents: BatchDocument[];
}

export interface BatchList {
  items: Batch[];
  total: number;
  limit: number;
  offset: number;
}
