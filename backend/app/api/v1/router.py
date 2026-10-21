"""Aggregate v1 API router."""
from fastapi import APIRouter

from .auth import router as auth_router
from .coding import router as coding_router
from .encounters import router as encounters_router
from .organizations import router as organizations_router
from .references import router as references_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(organizations_router)
api_router.include_router(encounters_router)
api_router.include_router(coding_router)
api_router.include_router(references_router)
