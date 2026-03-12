from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings
from app.web.router import router as web_router


STATIC_ROOT = Path(__file__).resolve().parent / "static"


def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.project_name,
        debug=settings.debug,
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    app.include_router(web_router)
    app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")
    return app


app = create_application()
