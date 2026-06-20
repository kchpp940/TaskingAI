import logging

from tkhelper.lifecycle import LifecycleManager, Phase, HookSeverity

logger = logging.getLogger(__name__)

manager = LifecycleManager("plugin")


async def _load_bundle_data():
    from app.cache import load_bundle_data

    bundle_ids = load_bundle_data()
    _load_bundle_data.__bundle_ids = bundle_ids


async def _load_all_bundle_handlers():
    from app.cache import load_all_bundle_handlers

    bundle_ids = getattr(_load_bundle_data, "__bundle_ids", [])
    load_all_bundle_handlers(bundle_ids)


async def _load_plugin_data():
    from app.cache import load_plugin_data

    bundle_ids = getattr(_load_bundle_data, "__bundle_ids", [])
    bundle_plugin_ids = load_plugin_data(bundle_ids)
    _load_plugin_data.__bundle_plugin_ids = bundle_plugin_ids


async def _load_all_plugin_handlers():
    from app.cache import load_all_plugin_handlers

    bundle_plugin_ids = getattr(_load_plugin_data, "__bundle_plugin_ids", {})
    load_all_plugin_handlers(bundle_plugin_ids)


async def _set_i18n_checksum():
    from app.cache import set_i18n_checksum

    set_i18n_checksum()


async def _clear_bundle_cache():
    from app.cache import clear_bundle_cache

    clear_bundle_cache()


async def _clear_plugin_cache():
    from app.cache import clear_plugin_cache

    clear_plugin_cache()


async def _clear_bundle_handlers():
    from app.cache import clear_bundle_handlers

    clear_bundle_handlers()


async def _clear_plugin_handlers():
    from app.cache import clear_plugin_handlers

    clear_plugin_handlers()


async def _clear_i18n_cache():
    from app.cache import clear_i18n_cache

    clear_i18n_cache()


manager.register_startup(
    name="load_bundle_data",
    phase=Phase.CACHE,
    fn=_load_bundle_data,
    severity=HookSeverity.CRITICAL,
    description="Load bundle data from YAML definitions",
)

manager.register_startup(
    name="load_plugin_data",
    phase=Phase.CACHE,
    fn=_load_plugin_data,
    severity=HookSeverity.CRITICAL,
    description="Load plugin data from YAML definitions",
)

manager.register_startup(
    name="load_bundle_handlers",
    phase=Phase.SERVICE,
    fn=_load_all_bundle_handlers,
    severity=HookSeverity.DEGRADABLE,
    description="Load and instantiate all bundle handler classes",
)

manager.register_startup(
    name="load_plugin_handlers",
    phase=Phase.SERVICE,
    fn=_load_all_plugin_handlers,
    severity=HookSeverity.DEGRADABLE,
    description="Load and instantiate all plugin handler classes",
)

manager.register_startup(
    name="set_i18n_checksum",
    phase=Phase.APPLICATION,
    fn=_set_i18n_checksum,
    severity=HookSeverity.DEGRADABLE,
    description="Compute and set i18n checksum for cache invalidation",
)

manager.register_shutdown(
    name="clear_i18n_cache",
    fn=_clear_i18n_cache,
    description="Clear i18n translation cache",
)

manager.register_shutdown(
    name="clear_plugin_handlers",
    fn=_clear_plugin_handlers,
    description="Clear plugin handler instances",
)

manager.register_shutdown(
    name="clear_bundle_handlers",
    fn=_clear_bundle_handlers,
    description="Clear bundle handler instances",
)

manager.register_shutdown(
    name="clear_plugin_cache",
    fn=_clear_plugin_cache,
    description="Clear plugin data cache",
)

manager.register_shutdown(
    name="clear_bundle_cache",
    fn=_clear_bundle_cache,
    description="Clear bundle data cache",
)
