"""Append-only audit events with a tamper-evident hash chain.

Each event's ``event_hash`` is ``HMAC-SHA256(AUDIT_HMAC_KEY, prev_hash + payload)``
where ``payload`` is a canonical JSON serialization of the event. The chain head is
stored in a singleton row locked with ``SELECT ... FOR UPDATE`` so concurrent
appends serialize (a no-op under SQLite, which serializes writes itself).

Integrity limits (documented, not over-claimed): the chain proves that, given the
HMAC key, the stored sequence has not been altered after the fact. It does not
prove events were *true* at write time, and a leaked ``AUDIT_HMAC_KEY`` breaks
integrity. See docs/SECURITY.md.
"""
import hashlib
import hmac
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.logging import redact
from ..models.audit import AuditChainState, AuditEvent

GENESIS_HASH = hashlib.sha256(b"mbc-audit-genesis").hexdigest()


def _canonical_payload(
    *,
    organization_id: str | None,
    actor_user_id: str | None,
    action: str,
    resource_type: str | None,
    resource_id: str | None,
    ip_address: str | None,
    user_agent: str | None,
    metadata: object,
    occurred_at: str,
) -> str:
    obj = {
        "organization_id": organization_id,
        "actor_user_id": actor_user_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "metadata": metadata,
        "occurred_at": occurred_at,
    }
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _compute_hash(prev_hash: str, payload: str) -> str:
    key = get_settings().audit_hmac_key.encode("utf-8")
    message = f"{prev_hash}:{payload}".encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def _load_metadata(metadata_json: str | None) -> object:
    return json.loads(metadata_json) if metadata_json is not None else None


class AuditService:
    @staticmethod
    def append(
        db: Session,
        *,
        organization_id: str | None,
        actor_user_id: str | None,
        action: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict | None = None,
    ) -> AuditEvent:
        """Append an audit event to the hash chain within the caller's transaction."""
        safe_metadata = redact(metadata) if isinstance(metadata, dict) else metadata
        occurred_at = datetime.now(timezone.utc).isoformat()

        head = db.execute(
            select(AuditChainState).where(AuditChainState.id == 1).with_for_update()
        ).scalar_one_or_none()
        if head is None:
            head = AuditChainState(id=1, current_hash=GENESIS_HASH, updated_at=occurred_at)
            db.add(head)
            db.flush()

        prev_hash = head.current_hash
        payload = _canonical_payload(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=safe_metadata,
            occurred_at=occurred_at,
        )
        event_hash = _compute_hash(prev_hash, payload)

        event = AuditEvent(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata_json=json.dumps(safe_metadata, sort_keys=True, default=str)
            if safe_metadata is not None
            else None,
            prev_hash=prev_hash,
            event_hash=event_hash,
            occurred_at=occurred_at,
        )
        db.add(event)
        db.flush()

        head.current_hash = event_hash
        head.updated_at = occurred_at
        return event

    @staticmethod
    def verify(db: Session) -> list[int]:
        """Recompute the chain from the beginning and return ids of tampered events."""
        events = db.execute(select(AuditEvent).order_by(AuditEvent.id.asc())).scalars().all()
        tampered: list[int] = []
        prev_hash = GENESIS_HASH
        for event in events:
            payload = _canonical_payload(
                organization_id=event.organization_id,
                actor_user_id=event.actor_user_id,
                action=event.action,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                ip_address=event.ip_address,
                user_agent=event.user_agent,
                metadata=_load_metadata(event.metadata_json),
                occurred_at=event.occurred_at,
            )
            expected = _compute_hash(prev_hash, payload)
            if event.prev_hash != prev_hash or event.event_hash != expected:
                tampered.append(event.id)
            prev_hash = event.event_hash
        return tampered
