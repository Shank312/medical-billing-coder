# Reference Data & Deterministic Code Validation

This document explains how code validation works and how to import appropriately
licensed or officially sourced datasets. **No authoritative code dataset is
invented or bundled with this project.**

## How validation works

Coding suggestions are AI **candidates only**. Each candidate is checked against a
versioned code set loaded per organization:

| Status | Meaning |
|---|---|
| `valid` | Code exists in a loaded set and is effective for the date of service |
| `date_invalid` | Code exists but is not effective for the date of service |
| `unknown` | A set is loaded, but the code is not present in it |
| `reference_data_unavailable` | No set is loaded for that code type — validation is impossible |

`reference_data_unavailable` is shown explicitly in the workspace and in exports; it
is never treated as "validated". A code with `unknown` is likewise never shown as
authoritative. Human review (`approved`/`rejected`/`corrected`) is the only path that
turns a suggestion into an accepted coding decision, and that decision is persisted
separately from the AI output.

## Supported code types

- `icd10cm` — ICD-10-CM (e.g., CMS public data)
- `hcpcs` — HCPCS Level II (e.g., CMS public data)
- `cpt` — CPT® (AMA-licensed; do **not** use public copies — obtain a license)

## Import endpoint

`POST /api/v1/code-references/import` (owner/admin, tenant-scoped). Request body:

```json
{
  "code_type": "icd10cm",
  "source": "CMS",
  "version": "2025",
  "effective_start": "2024-10-01",
  "effective_end": "2025-09-30",
  "codes": [
    { "code": "F32.9", "description": "Major depressive disorder, recurrent, unspecified", "is_billable": true }
  ]
}
```

- `code_type` ∈ `icd10cm` | `hcpcs` | `cpt`.
- `source` is a short provenance label (e.g., `CMS`, `AMA-CPT-2025`).
- `version` + `source` are unique together (`code_set_exists` conflict on re-import).
- Each `codes[]` entry may carry its own `effective_start`/`effective_end` for
  per-code effective dates; `is_billable` defaults to `true`.
- Imports are audited (`reference_data.imported`) with `code_type`, `source`,
  `version`, and `record_count` — never the code descriptions.

### Preparing an official dataset

A typical tabular source (e.g., the CMS ICD-10-CM order file) can be transformed
into the import format with a short script. Example (illustrative only — adapt the
column mapping to the licensed source you are using):

```python
import csv, json, urllib.request

# Download a specific, dated release (replace with your licensed/official URL).
rows = []
with open("icd10cm_order_2025.txt", newline="") as f:
    for line in f:
        code = line[6:13].strip()
        desc = line[77:].strip()
        if code and desc:
            rows.append({"code": code, "description": desc, "is_billable": True})

payload = {
    "code_type": "icd10cm",
    "source": "CMS",
    "version": "2025",
    "effective_start": "2024-10-01",
    "effective_end": "2025-09-30",
    "codes": rows,
}
print(json.dumps(payload))
```

Do **not** commit downloaded datasets or derived code lists to the repository. Store
them in a private, access-controlled location and import them through the API by an
authorized owner/admin.

### CPT® licensing

CPT® codes are copyrighted by the AMA. Using them in production requires an AMA
license and typically an integrated data file. Do not use unlicensed public copies.
The `cpt` code type is supported by the import endpoint so that a licensed data file
can be loaded; the project ships no CPT data.

## Testing lookups

After importing, verify with the lookup endpoint (or the workspace validation badge):

`GET /api/v1/code-references/lookup?code_type=icd10cm&code=F32.9&date_of_service=2025-03-15`

```json
{ "code": "F32.9", "code_type": "icd10cm", "status": "valid", "description": "…", "version": "2025", "source": "CMS" }
```

Automated tests use `SYNTHETIC_TEST` source codes only (e.g., `F32.9`, `90837`) and
never assert that a synthetic code is authoritative for real billing.
