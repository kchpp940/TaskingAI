from typing import List

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from starlette_prometheus import metrics, PrometheusMiddleware
from app.routes import routes
import logging
import os
from app.error.exception_handlers import *

import warnings

warnings.filterwarnings("ignore", module="pydantic")

log_level = os.environ.get("LOG_LEVEL", "INFO")

logger = logging.getLogger()
logger.setLevel(log_level)

formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


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


def init_route_logger(filters: List[str]):

    logger = logging.getLogger("uvicorn.access")
    if logger.handlers:
        handler = logger.handlers[0]
        handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    else:
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    class IgnoreRouteLogFilter(logging.Filter):
        def filter(self, record):
            message = record.getMessage()
            return not any([f in message for f in filters])

    logger.addFilter(IgnoreRouteLogFilter())


def create_app():

    app = FastAPI(
        title="TaskingAI-Inference",
        version=CONFIG.VERSION,
        servers=[{f"url": f"http://localhost:{CONFIG.SERVICE_PORT}"}],
        lifespan=lifespan,
    )

    init_route_logger(filters=[' HTTP/1.1" 200'])
    app.exception_handler(HTTPException)(custom_http_exception_handler)
    app.exception_handler(RequestValidationError)(custom_request_validation_error_handler)
    app.exception_handler(Exception)(custom_exception_handler)

    app.add_middleware(PrometheusMiddleware, filter_unhandled_paths=True)
    app.add_route("/prometheus/metrics", metrics)

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
