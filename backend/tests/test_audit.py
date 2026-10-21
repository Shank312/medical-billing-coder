"""Audit append, ordering, and tamper-detection tests."""
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.audit import AuditEvent
from app.services.audit import AuditService


def test_audit_append_and_chain_order(client, register):
    register("audit@example.com", "Audit Org")
    db = SessionLocal()
    try:
        events = list(db.execute(select(AuditEvent).order_by(AuditEvent.id.asc())).scalars())
        assert len(events) == 2  # organization.created + user.registered
        assert events[0].prev_hash != ""
        assert events[1].prev_hash == events[0].event_hash
        assert AuditService.verify(db) == []
    finally:
        db.close()


def test_audit_tamper_detection(client, register):
    register("audit2@example.com", "Audit Org 2")
    db = SessionLocal()
    try:
        first = db.execute(select(AuditEvent).order_by(AuditEvent.id.asc())).scalars().first()
        first.metadata_json = '{"tampered": true}'
        db.commit()
        tampered = AuditService.verify(db)
        assert first.id in tampered
    finally:
        db.close()


def test_failed_login_is_audited(client, register):
    register("audit3@example.com", "Audit Org 3")
    client.post(
        "/api/v1/auth/login",
        json={"email": "audit3@example.com", "password": "wrong-password"},
    )
    db = SessionLocal()
    try:
        actions = [
            e.action
            for e in db.execute(select(AuditEvent).order_by(AuditEvent.id.asc())).scalars()
        ]
        assert "auth.login_failed" in actions
        # Failed-login metadata must not leak the password.
        failed = db.execute(
            select(AuditEvent).where(AuditEvent.action == "auth.login_failed")
        ).scalars().first()
        assert "wrong-password" not in (failed.metadata_json or "")
    finally:
        db.close()
