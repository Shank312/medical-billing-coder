"""Role-based access control tests (deny-by-default)."""
import pytest

TEST_PASSWORD = "correct-horse-battery-staple-123!"


def _login_as(client, email, organization_id=None):
    body = {"email": email, "password": TEST_PASSWORD}
    if organization_id:
        body["organization_id"] = organization_id
    response = client.post("/api/v1/auth/login", json=body)
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _add_member(client, owner_access, org_id, email, role):
    response = client.post(
        f"/api/v1/organizations/{org_id}/users",
        json={"email": email, "full_name": "Member Person", "role": role},
        headers={"Authorization": f"Bearer {owner_access}"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_owner_can_mutate(client, register, auth_headers):
    data = register("owner@rbac.example.com", "Rbac Org")
    org_id = data["organization"]["id"]
    response = client.patch(
        f"/api/v1/organizations/{org_id}",
        json={"name": "Renamed Org"},
        headers=auth_headers(data["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed Org"


def test_admin_can_mutate(client, register, auth_headers):
    owner = register("owner@rbac2.example.com", "Rbac2 Org")
    org_id = owner["organization"]["id"]
    register("admin@rbac2.example.com", "Admin Own Org")
    _add_member(client, owner["access_token"], org_id, "admin@rbac2.example.com", "admin")

    access = _login_as(client, "admin@rbac2.example.com", org_id)
    response = client.patch(
        f"/api/v1/organizations/{org_id}",
        json={"name": "Renamed by admin"},
        headers=auth_headers(access),
    )
    assert response.status_code == 200


@pytest.mark.parametrize("role", ["provider", "coder", "biller", "auditor", "read_only"])
def test_read_only_roles_denied_mutation(client, register, auth_headers, role):
    owner = register("owner@rbac3.example.com", "Rbac3 Org")
    org_id = owner["organization"]["id"]

    register(f"{role}@rbac3.example.com", f"{role} own org")
    _add_member(client, owner["access_token"], org_id, f"{role}@rbac3.example.com", role)

    access = _login_as(client, f"{role}@rbac3.example.com", org_id)
    response = client.patch(
        f"/api/v1/organizations/{org_id}",
        json={"name": "should not work"},
        headers=auth_headers(access),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_read_only_role_can_read(client, register, auth_headers):
    owner = register("owner@rbac4.example.com", "Rbac4 Org")
    org_id = owner["organization"]["id"]
    register("coder@rbac4.example.com", "Coder Own Org")
    _add_member(client, owner["access_token"], org_id, "coder@rbac4.example.com", "coder")

    access = _login_as(client, "coder@rbac4.example.com", org_id)
    response = client.get(f"/api/v1/organizations/{org_id}", headers=auth_headers(access))
    assert response.status_code == 200


def test_unauthenticated_denied(client):
    response = client.get("/api/v1/organizations/some-org-id")
    assert response.status_code == 401
