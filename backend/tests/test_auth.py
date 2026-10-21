"""Authentication flow tests: register, login, logout, refresh rotation,
reuse detection, session revocation, MFA, and cookie attributes."""
import pyotp

TEST_PASSWORD = "correct-horse-battery-staple-123!"


def test_register_and_login(client, register):
    data = register("owner@example.com", "Acme Health")
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["user"]["email"] == "owner@example.com"
    assert data["organization"]["name"] == "Acme Health"

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": TEST_PASSWORD},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]


def test_login_wrong_password(client, register):
    register("owner@example.com", "Acme Health")
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "totally-wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_register_duplicate_email(client, register):
    register("owner@example.com", "Acme Health")
    response = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Other Org",
            "full_name": "Someone Else",
            "email": "owner@example.com",
            "password": TEST_PASSWORD,
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_in_use"


def test_me(client, register, auth_headers):
    data = register("owner@example.com", "Acme Health")
    response = client.get("/api/v1/auth/me", headers=auth_headers(data["access_token"]))
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "owner@example.com"
    assert response.json()["organization"]["name"] == "Acme Health"


def test_me_requires_auth(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_refresh_rotation_and_reuse_detection(client, register):
    data = register("owner@example.com", "Acme Health")
    refresh1 = data["refresh_token"]

    first = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh1})
    assert first.status_code == 200, first.text
    refresh2 = first.json()["refresh_token"]
    assert refresh2 != refresh1

    # Reusing the rotated token must be detected and revoke the family.
    reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh1})
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "refresh_reuse"

    # The newly-issued token was revoked as part of the family.
    revoked = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh2})
    assert revoked.status_code == 401


def test_logout_revokes_refresh(client, register):
    data = register("owner@example.com", "Acme Health")
    refresh = data["refresh_token"]

    logout = client.post("/api/v1/auth/logout", json={"refresh_token": refresh})
    assert logout.status_code == 200

    after = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert after.status_code == 401


def test_revoke_all_sessions(client, register, auth_headers):
    data = register("owner@example.com", "Acme Health")
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": TEST_PASSWORD},
    )
    refresh_a = data["refresh_token"]
    refresh_b = login.json()["refresh_token"]

    response = client.post(
        "/api/v1/auth/sessions/revoke-all", headers=auth_headers(data["access_token"])
    )
    assert response.status_code == 200

    assert client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_a}).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_b}).status_code == 401


def test_refresh_cookie_attributes(client, register):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Acme Health",
            "full_name": "Test Person",
            "email": "owner@example.com",
            "password": TEST_PASSWORD,
        },
    )
    set_cookie = response.headers.get("set-cookie", "")
    assert "refresh_token=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=strict" in set_cookie
    assert "secure" not in set_cookie.lower()  # COOKIE_SECURE=false in tests


def test_mfa_enroll_verify_and_required_login(client, register, auth_headers):
    data = register("owner@example.com", "Acme Health")
    headers = auth_headers(data["access_token"])

    enroll = client.post("/api/v1/auth/mfa/enroll", headers=headers)
    assert enroll.status_code == 200, enroll.text
    secret = enroll.json()["secret"]
    assert enroll.json()["otpauth_uri"].startswith("otpauth://totp/")

    code = pyotp.TOTP(secret).now()
    verify = client.post("/api/v1/auth/mfa/verify", json={"code": code}, headers=headers)
    assert verify.status_code == 200, verify.text

    # Login now requires a valid MFA code.
    missing = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": TEST_PASSWORD},
    )
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "mfa_required"

    wrong = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": TEST_PASSWORD, "mfa_code": "000000"},
    )
    assert wrong.status_code == 401

    good = client.post(
        "/api/v1/auth/login",
        json={
            "email": "owner@example.com",
            "password": TEST_PASSWORD,
            "mfa_code": pyotp.TOTP(secret).now(),
        },
    )
    assert good.status_code == 200, good.text


def test_mfa_secret_never_stored_plaintext(client, register, auth_headers):
    from app.db.session import SessionLocal
    from app.models.mfa import MfaConfig
    from sqlalchemy import select

    data = register("owner@example.com", "Acme Health")
    client.post("/api/v1/auth/mfa/enroll", headers=auth_headers(data["access_token"]))

    db = SessionLocal()
    try:
        config = db.execute(select(MfaConfig).limit(1)).scalar_one()
        assert config.secret_encrypted != ""
        assert "JBSWY3DPEHPK3PXP" not in config.secret_encrypted
        # Fernet ciphertext starts with a version byte; it is not the raw base32 secret.
        assert config.secret_encrypted.startswith("gAAAA")
    finally:
        db.close()
