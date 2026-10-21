"""Cross-tenant access denial tests (read/write/update/delete)."""


def test_cross_tenant_read_denied(client, register, auth_headers):
    org_a = register("owner-a@example.com", "Org A")
    org_b = register("owner-b@example.com", "Org B")
    response = client.get(
        f"/api/v1/organizations/{org_b['organization']['id']}",
        headers=auth_headers(org_a["access_token"]),
    )
    assert response.status_code == 404


def test_cross_tenant_update_denied(client, register, auth_headers):
    org_a = register("owner-a@example.com", "Org A")
    org_b = register("owner-b@example.com", "Org B")
    response = client.patch(
        f"/api/v1/organizations/{org_b['organization']['id']}",
        json={"name": "hacked"},
        headers=auth_headers(org_a["access_token"]),
    )
    assert response.status_code == 404


def test_cross_tenant_write_denied(client, register, auth_headers):
    org_a = register("owner-a@example.com", "Org A")
    org_b = register("owner-b@example.com", "Org B")
    response = client.post(
        f"/api/v1/organizations/{org_b['organization']['id']}/users",
        json={"email": "intruder@example.com", "full_name": "X", "role": "admin"},
        headers=auth_headers(org_a["access_token"]),
    )
    assert response.status_code == 404


def test_cross_tenant_delete_denied(client, register, auth_headers):
    org_a = register("owner-a@example.com", "Org A")
    org_b = register("owner-b@example.com", "Org B")
    response = client.delete(
        f"/api/v1/organizations/{org_b['organization']['id']}/users/{org_b['user']['id']}",
        headers=auth_headers(org_a["access_token"]),
    )
    assert response.status_code == 404


def test_cross_tenant_list_denied(client, register, auth_headers):
    org_a = register("owner-a@example.com", "Org A")
    org_b = register("owner-b@example.com", "Org B")
    response = client.get(
        f"/api/v1/organizations/{org_b['organization']['id']}/users",
        headers=auth_headers(org_a["access_token"]),
    )
    assert response.status_code == 404


def test_same_tenant_access_allowed(client, register, auth_headers):
    org = register("owner-c@example.com", "Org C")
    org_id = org["organization"]["id"]

    read = client.get(f"/api/v1/organizations/{org_id}", headers=auth_headers(org["access_token"]))
    assert read.status_code == 200

    update = client.patch(
        f"/api/v1/organizations/{org_id}",
        json={"name": "Org C Renamed"},
        headers=auth_headers(org["access_token"]),
    )
    assert update.status_code == 200
    assert update.json()["name"] == "Org C Renamed"
