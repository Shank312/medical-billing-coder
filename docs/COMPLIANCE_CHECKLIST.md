# Compliance Checklist

> **Important:** this project is designed to *support* HIPAA-regulated workloads.
> It is **not** HIPAA-compliant out of the box, and no compliance claim is made by
> the presence of encryption or other controls. HIPAA compliance is a property of
> the *operating environment* and *organization*, not just the software.

Use this checklist when evaluating a production deployment.

## 1. Business Associate Agreements (BAAs)

- [ ] Execute a BAA with the hosting/cloud provider (compute, database, object storage).
- [ ] Execute a BAA with the AI provider **before** transmitting any PHI.
- [ ] Execute BAAs with any transcription, scanning, or logging provider.
- [ ] Keep a register of every provider that touches PHI and their BAA status.

## 2. Provider eligibility (AI and document processing)

For every provider that may receive PHI:

- [ ] Verify the provider offers a HIPAA-eligible configuration and signs a BAA.
- [ ] Confirm the provider's data-retention and training policy in writing.
- [ ] **Never** claim a provider's "no-training" policy alone establishes compliance.
- [ ] **Never** claim a "zero-data-retention" capability that the provider does not
      contractually guarantee.
- [ ] Configure the AI adapter to send **minimum necessary** data only (Phase 2);
      never full records or unnecessary identifiers.
- [ ] Never transmit real PHI to an unapproved provider. Development and tests use
      synthetic data only.

## 3. Technical controls (implemented in Phase 1)

- [x] Tenant isolation at every DB access (404 for cross-tenant).
- [x] Role-based access control (deny-by-default).
- [x] Argon2id password hashing.
- [x] Short-lived access tokens + hashed rotating refresh tokens + reuse detection.
- [x] TOTP MFA with encrypted-at-rest secrets.
- [x] Append-only, tamper-evident audit log (hash chain).
- [x] Redacted logs and a normalized error contract (no stack traces to clients).
- [x] Rate limiting.
- [x] Secrets via environment / managed store (none committed).

## 4. Technical controls (still to implement)

- [ ] TLS enforcement end-to-end in production (terminate TLS; set `COOKIE_SECURE=true`).
- [ ] Managed secrets + automated key rotation.
- [ ] Backup, restore, and retention/deletion workflows.
- [ ] Upload validation, size/type allow-lists, and malware scanning (Phase 4).
- [ ] Data classification and field-level encryption for stored PHI.
- [ ] Database-level append-only enforcement and external audit-chain export.
- [ ] Email verification and account recovery.
- [ ] Session/timeout hardening and MFA step-up policies.

## 5. Operational / administrative controls

- [ ] Access reviews for privileged roles.
- [ ] Least-privilege for operations and infrastructure.
- [ ] Incident response and breach-notification procedures.
- [ ] Security awareness training for staff with PHI access.
- [ ] Change management and audit-log retention policy.
- [ ] Penetration testing and independent security assessment before production.

## 6. AI coding workflow safeguards (Phase 2+)

- [ ] Treat AI output as **suggestions**, never verified facts; require human review.
- [ ] Validate all codes against authoritative, versioned code sets with
      date-of-service validity and payer-specific rules.
- [ ] Never auto-submit claims.
- [ ] Telehealth mentions trigger contextual review, never unconditional modifiers.
- [ ] Log AI metadata (model, prompt version, token counts), not clinical text.

## Status

Phase 1 implements the technical foundations listed in section 3. Sections 1, 2,
4, 5, and 6 remain open and must be completed — with independent verification —
before any production or PHI use.
