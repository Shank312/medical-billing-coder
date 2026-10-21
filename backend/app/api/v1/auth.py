"""Authentication endpoints: register, login, refresh, logout, MFA, current user."""
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...core.errors import ForbiddenError, UnauthorizedError
from ...core.rate_limit import configured_rate_limit_dependency
from ...core.security import build_refresh_cookie_params
from ...db.session import get_db_session
from ...repositories.organizations import OrganizationRepository
from ...repositories.users import UserRepository
from ...schemas.auth import AuthResponse, LoginRequest, MeResponse, RefreshRequest, RegisterRequest
from ...schemas.common import MessageResponse
from ...schemas.mfa import MfaDisableRequest, MfaEnrollResponse, MfaVerifyRequest
from ...schemas.organization import OrganizationOut
from ...schemas.user import UserOut
from ..deps import AuthContext, get_auth_context, request_info

router = APIRouter(prefix="/auth", tags=["auth"])

_auth_rate_limit = Depends(configured_rate_limit_dependency("rate_limit_auth", key_prefix="auth"))


def _check_origin(request: Request) -> None:
    """Defense-in-depth CSRF check for cookie-based requests."""
    origin = request.headers.get("origin")
    if not origin:
        return
    settings = get_settings()
    allowed = {o.rstrip("/") for o in settings.cors_origins}
    if origin.rstrip("/") not in allowed:
        raise ForbiddenError("Cross-origin request rejected")


def _get_user_or_401(db: Session, user_id: str):
    user = UserRepository(db).get(user_id)
    if user is None:
        raise UnauthorizedError("User not found")
    return user


def _cookie_path() -> str:
    return f"{get_settings().api_v1_prefix}/auth"


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=201,
    dependencies=[_auth_rate_limit],
)
def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db_session),
):
    ip, ua = request_info(request)
    from ...services import auth as auth_service

    try:
        org, user, access_token, raw_refresh, expires_in = auth_service.register(
            db,
            organization_name=body.organization_name,
            organization_slug=body.organization_slug,
            full_name=body.full_name,
            email=body.email,
            password=body.password,
            ip_address=ip,
            user_agent=ua,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    response.set_cookie(**build_refresh_cookie_params(raw_refresh))
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        refresh_token=raw_refresh,
        user=UserOut.model_validate(user),
        organization=OrganizationOut.model_validate(org),
    )


@router.post("/login", response_model=AuthResponse, dependencies=[_auth_rate_limit])
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db_session),
):
    ip, ua = request_info(request)
    from ...services import auth as auth_service

    try:
        result = auth_service.login(
            db,
            email=body.email,
            password=body.password,
            organization_id=body.organization_id,
            mfa_code=body.mfa_code,
            ip_address=ip,
            user_agent=ua,
        )
    except (UnauthorizedError, ForbiddenError):
        # Persist the failed-login audit event, then surface the error.
        db.commit()
        raise
    except Exception:
        db.rollback()
        raise

    db.commit()
    org, user, _roles, access_token, raw_refresh, expires_in = result
    response.set_cookie(**build_refresh_cookie_params(raw_refresh))
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        refresh_token=raw_refresh,
        user=UserOut.model_validate(user),
        organization=OrganizationOut.model_validate(org),
    )


@router.post("/refresh", response_model=AuthResponse, dependencies=[_auth_rate_limit])
def refresh_token(
    request: Request,
    response: Response,
    body: RefreshRequest | None = None,
    db: Session = Depends(get_db_session),
):
    _check_origin(request)
    ip, ua = request_info(request)
    token = (body.refresh_token if body else None) or request.cookies.get("refresh_token")
    from ...services import auth as auth_service

    try:
        result = auth_service.refresh(db, refresh_token=token, ip_address=ip, user_agent=ua)
    except UnauthorizedError:
        # Persist reuse/expiry audit events before surfacing the error.
        db.commit()
        raise
    except Exception:
        db.rollback()
        raise

    db.commit()
    org, user, _roles, access_token, raw_refresh, expires_in = result
    response.set_cookie(**build_refresh_cookie_params(raw_refresh))
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        refresh_token=raw_refresh,
        user=UserOut.model_validate(user),
        organization=OrganizationOut.model_validate(org),
    )


@router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request,
    response: Response,
    body: RefreshRequest | None = None,
    db: Session = Depends(get_db_session),
):
    ip, ua = request_info(request)
    token = (body.refresh_token if body else None) or request.cookies.get("refresh_token")
    from ...services import auth as auth_service

    if token:
        try:
            auth_service.logout(db, refresh_token=token, ip_address=ip, user_agent=ua)
            db.commit()
        except Exception:
            db.rollback()
            raise

    response.delete_cookie("refresh_token", path=_cookie_path())
    return MessageResponse(message="Logged out")


@router.post("/sessions/revoke-all", response_model=MessageResponse)
def revoke_all_sessions(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db_session),
):
    ip, ua = request_info(request)
    from ...services import auth as auth_service

    try:
        auth_service.revoke_all_sessions(
            db,
            user_id=auth.user_id,
            organization_id=auth.organization_id,
            ip_address=ip,
            user_agent=ua,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return MessageResponse(message="All sessions revoked")


@router.get("/me", response_model=MeResponse)
def me(
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db_session),
):
    user = _get_user_or_401(db, auth.user_id)
    organization = OrganizationRepository(db).get(auth.organization_id)
    if organization is None:
        raise UnauthorizedError("Organization not found")
    return MeResponse(
        user=UserOut.model_validate(user),
        organization=OrganizationOut.model_validate(organization),
        roles=auth.roles,
    )


@router.post("/mfa/enroll", response_model=MfaEnrollResponse)
def mfa_enroll(
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db_session),
):
    ip, ua = request_info(request)
    user = _get_user_or_401(db, auth.user_id)
    from ...services import mfa as mfa_service

    try:
        secret, uri = mfa_service.enroll(
            db, user=user, organization_id=auth.organization_id, ip_address=ip, user_agent=ua
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return MfaEnrollResponse(secret=secret, otpauth_uri=uri)


@router.post("/mfa/verify", response_model=MessageResponse)
def mfa_verify(
    body: MfaVerifyRequest,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db_session),
):
    ip, ua = request_info(request)
    user = _get_user_or_401(db, auth.user_id)
    from ...services import mfa as mfa_service

    try:
        mfa_service.verify_and_enable(
            db, user=user, organization_id=auth.organization_id, code=body.code,
            ip_address=ip, user_agent=ua,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return MessageResponse(message="MFA enabled")


@router.post("/mfa/disable", response_model=MessageResponse)
def mfa_disable(
    body: MfaDisableRequest,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db_session),
):
    ip, ua = request_info(request)
    user = _get_user_or_401(db, auth.user_id)
    from ...services import mfa as mfa_service

    try:
        mfa_service.disable(
            db, user=user, organization_id=auth.organization_id, password=body.password,
            code=body.code, ip_address=ip, user_agent=ua,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return MessageResponse(message="MFA disabled")
