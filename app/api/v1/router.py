from fastapi import APIRouter

from app.api.v1.endpoints.documents import router as documents_router
from app.api.v1.endpoints.facts import router as facts_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.metrics import router as metrics_router
from app.api.v1.endpoints.review import router as review_router


api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(documents_router)
api_router.include_router(facts_router)
api_router.include_router(metrics_router)
api_router.include_router(review_router)
