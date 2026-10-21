"""Server-side encounter list filtering, sorting, and pagination tests."""
import json

from app.ai.mock import MockProvider

TEST_PASSWORD = "correct-horse-battery-staple-123!"
NOTE = "Patient presents with hypertension."

EMPTY_OUTPUT = json.dumps(
    {"diagnoses": [], "procedures": [], "modifiers": [], "missing_documentation": [], "contradictions": []}
)

PENDING_OUTPUT = json.dumps(
    {
        "diagnoses": [{"code": "F32.9", "code_type": "icd10cm", "evidence": []}],
        "procedures": [],
        "modifiers": [],
        "missing_documentation": [],
        "contradictions": [],
    }
)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _register(client, email):
    response = client.post(
        "/api/v1/auth/register",
        json={"organization_name": f"Org {email}", "full_name": "Person", "email": email, "password": TEST_PASSWORD},
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def _create(client, token, patient_ref, date="2025-01-01", encounter_type="office visit"):
    response = client.post(
        "/api/v1/encounters",
        json={"date_of_service": date, "note": NOTE, "patient_reference": patient_ref, "encounter_type": encounter_type},
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _list(client, token, **params):
    return client.get("/api/v1/encounters", params=params, headers=_auth(token))


def test_list_search_is_case_insensitive(client):
    token = _register(client, "owner@search.example.com")
    _create(client, token, "MRN-ABC-1")
    _create(client, token, "MRN-XYZ-2")

    result = _list(client, token, search="abc").json()
    assert result["total"] == 1
    assert result["items"][0]["patient_reference"] == "MRN-ABC-1"


def test_list_sort_by_date(client):
    token = _register(client, "owner@sort.example.com")
    _create(client, token, "MRN-1", date="2025-01-01")
    _create(client, token, "MRN-2", date="2025-03-01")
    _create(client, token, "MRN-3", date="2025-02-01")

    asc = _list(client, token, sort="date_of_service", order="asc").json()
    assert [e["patient_reference"] for e in asc["items"]] == ["MRN-1", "MRN-3", "MRN-2"]

    desc = _list(client, token, sort="date_of_service", order="desc").json()
    assert [e["patient_reference"] for e in desc["items"]] == ["MRN-2", "MRN-3", "MRN-1"]


def test_list_status_filter_coded_and_not_coded(client, monkeypatch):
    monkeypatch.setattr("app.services.coding.get_provider", lambda: MockProvider(response_json=EMPTY_OUTPUT))
    token = _register(client, "owner@status.example.com")
    coded = _create(client, token, "MRN-CODED")
    _create(client, token, "MRN-NOT")
    client.post(f"/api/v1/encounters/{coded['id']}/code", headers=_auth(token))

    coded_result = _list(client, token, status="coded").json()
    assert [e["patient_reference"] for e in coded_result["items"]] == ["MRN-CODED"]

    not_coded_result = _list(client, token, status="not_coded").json()
    assert [e["patient_reference"] for e in not_coded_result["items"]] == ["MRN-NOT"]


def test_list_status_filter_pending(client, monkeypatch):
    monkeypatch.setattr("app.services.coding.get_provider", lambda: MockProvider(response_json=PENDING_OUTPUT))
    token = _register(client, "owner@pending.example.com")
    encounter = _create(client, token, "MRN-PENDING")
    client.post(f"/api/v1/encounters/{encounter['id']}/code", headers=_auth(token))

    result = _list(client, token, status="pending").json()
    assert [e["patient_reference"] for e in result["items"]] == ["MRN-PENDING"]


def test_list_pagination_total(client):
    token = _register(client, "owner@page.example.com")
    for i in range(3):
        _create(client, token, f"MRN-{i}")

    page1 = _list(client, token, limit=2, offset=0).json()
    assert page1["total"] == 3
    assert len(page1["items"]) == 2

    page2 = _list(client, token, limit=2, offset=2).json()
    assert page2["total"] == 3
    assert len(page2["items"]) == 1


def test_list_invalid_params(client):
    token = _register(client, "owner@invalid.example.com")

    response = _list(client, token, sort="bogus")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_sort"

    assert _list(client, token, status="bogus").json()["error"]["code"] == "invalid_status"
    assert _list(client, token, order="bogus").json()["error"]["code"] == "invalid_order"


def test_list_tenant_isolation(client):
    token_a = _register(client, "a@tenant.example.com")
    token_b = _register(client, "b@tenant.example.com")
    _create(client, token_a, "MRN-SECRET-A")

    result = _list(client, token_b, search="SECRET").json()
    assert result["total"] == 0
    assert result["items"] == []
