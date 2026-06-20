import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from tkhelper.lifecycle import LifecycleManager, Phase, HookSeverity

logger = logging.getLogger(__name__)

_scheduler = AsyncIOScheduler()
manager = LifecycleManager("backend")


async def _init_database():
    from app.database import init_database

    await init_database()


async def _close_database():
    from app.database import close_database

    await close_database()


async def _redis_health_check():
    from app.database import redis_conn

    ok = await redis_conn.health_check()
    if not ok:
        raise RuntimeError("Redis health check failed after initialization")


async def _check_contract():
    from app.utils.artifact_schema_validator import load_schema, get_schema_version

    schema = load_schema()
    version = get_schema_version()
    logger.info(f"Artifact contract schema loaded, version={version}")


async def _start_scheduler():
    from app.services.model import sync_model_schema_data
    from app.services.tool import sync_plugin_data

    async def sync_data():
        try:
            logger.info("Syncing model schema data...")
            await sync_model_schema_data()
            logger.info("Syncing plugin data...")
            await sync_plugin_data()
        except Exception:
            logger.error("Failed to sync data in scheduler tick.")

    _scheduler.add_job(sync_data, "interval", minutes=1)
    _scheduler.start()


async def _stop_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)


async def _first_sync():
    from app.services.model import sync_model_schema_data
    from app.services.tool import sync_plugin_data

    logger.info("Syncing model schema data...")
    await sync_model_schema_data()
    logger.info("Syncing plugin data...")
    await sync_plugin_data()


async def _create_default_admin():
    from app.services.auth.admin import create_default_admin_if_needed
    from app.config import CONFIG

    if CONFIG.WEB:
        await create_default_admin_if_needed()


manager.register_startup(
    name="init_database",
    phase=Phase.INFRASTRUCTURE,
    fn=_init_database,
    severity=HookSeverity.CRITICAL,
    description="Initialize PostgreSQL pool and Redis connection",
)

manager.register_startup(
    name="redis_health_check",
    phase=Phase.INFRASTRUCTURE,
    fn=_redis_health_check,
    severity=HookSeverity.DEGRADABLE,
    description="Verify Redis is responsive after initialization",
)

manager.register_startup(
    name="check_contract",
    phase=Phase.CACHE,
    fn=_check_contract,
    severity=HookSeverity.DEGRADABLE,
    description="Load and validate artifact contract schema",
)

manager.register_startup(
    name="first_sync",
    phase=Phase.SERVICE,
    fn=_first_sync,
    severity=HookSeverity.CRITICAL,
    description="Perform initial data sync from inference and plugin services",
)

manager.register_startup(
    name="start_scheduler",
    phase=Phase.SERVICE,
    fn=_start_scheduler,
    severity=HookSeverity.DEGRADABLE,
    description="Start periodic data sync scheduler",
)

manager.register_startup(
    name="create_default_admin",
    phase=Phase.APPLICATION,
    fn=_create_default_admin,
    severity=HookSeverity.DEGRADABLE,
    description="Create default admin user if needed (web mode only)",
)

manager.register_shutdown(
    name="stop_scheduler",
    fn=_stop_scheduler,
    description="Stop the periodic sync scheduler",
)

manager.register_shutdown(
    name="close_database",
    fn=_close_database,
    description="Close PostgreSQL pool and Redis connection",
)
