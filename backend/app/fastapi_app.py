import logging
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from tkhelper.error.exception_handlers import *
from tkhelper.utils import init_logger

from contextlib import asynccontextmanager

init_logger()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.lifecycle import manager

    startup_ok = await manager.run_startup()
    manager.attach_to_app(app)

    if not startup_ok:
        raise RuntimeError(
            f"Service failed to start. Critical initialization failed. "
            f"Failed phase: {manager.state.failed_phase}, "
            f"reason: {manager.state.failure_reason}"
        )

    if manager.degraded_services:
        logger.warning(
            f"Service starting in degraded mode: {manager.degraded_services}"
        )

    yield

    await manager.run_shutdown()


def create_app():
    import os
    from app.config import CONFIG
    from app.routes import routes
    from fastapi.staticfiles import StaticFiles

    app = FastAPI(title="TaskingAI-Community", version=CONFIG.VERSION, lifespan=lifespan)

    imgs_volume_path = os.path.abspath(os.path.join(CONFIG.PATH_TO_VOLUME, "imgs"))
    if not os.path.exists(imgs_volume_path):
        os.makedirs(imgs_volume_path)
    app.mount("/imgs", StaticFiles(directory=imgs_volume_path), name="imgs")

    add_exception_handlers(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(routes)
    return app


app = create_app()
