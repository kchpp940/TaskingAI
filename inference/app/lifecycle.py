import logging

from tkhelper.lifecycle import LifecycleManager, Phase, HookSeverity

logger = logging.getLogger(__name__)

manager = LifecycleManager("inference")


async def _load_provider_data_and_store():
    from app.cache import load_provider_data

    provider_ids = load_provider_data()
    _load_provider_data_and_store.__provider_ids = provider_ids


async def _load_model_schema_from_stored():
    from app.cache import load_model_schema_data

    provider_ids = getattr(_load_provider_data_and_store, "__provider_ids", [])
    load_model_schema_data(provider_ids)


async def _load_text_embedding_from_stored():
    from app.cache import load_all_text_embedding_models

    provider_ids = getattr(_load_provider_data_and_store, "__provider_ids", [])
    load_all_text_embedding_models(provider_ids)


async def _load_chat_completion_from_stored():
    from app.cache import load_all_chat_completion_models

    provider_ids = getattr(_load_provider_data_and_store, "__provider_ids", [])
    load_all_chat_completion_models(provider_ids)


async def _set_i18n_checksum():
    from app.utils import set_i18n_checksum

    set_i18n_checksum()


async def _clear_provider_cache():
    from app.cache import clear_provider_cache

    clear_provider_cache()


async def _clear_model_schema_cache():
    from app.cache import clear_model_schema_cache

    clear_model_schema_cache()


async def _clear_chat_completion_models():
    from app.cache import clear_chat_completion_models

    clear_chat_completion_models()


async def _clear_text_embedding_models():
    from app.cache import clear_text_embedding_models

    clear_text_embedding_models()


async def _clear_rerank_models():
    from app.cache import clear_rerank_models

    clear_rerank_models()


async def _clear_i18n_cache():
    from app.utils import clear_i18n_cache

    clear_i18n_cache()


manager.register_startup(
    name="load_provider_data",
    phase=Phase.CACHE,
    fn=_load_provider_data_and_store,
    severity=HookSeverity.CRITICAL,
    description="Load provider data from YAML definitions",
)

manager.register_startup(
    name="load_model_schema_data",
    phase=Phase.CACHE,
    fn=_load_model_schema_from_stored,
    severity=HookSeverity.CRITICAL,
    description="Load model schema data for all providers",
)

manager.register_startup(
    name="load_text_embedding_models",
    phase=Phase.SERVICE,
    fn=_load_text_embedding_from_stored,
    severity=HookSeverity.DEGRADABLE,
    description="Load text embedding model implementations for all providers",
)

manager.register_startup(
    name="load_chat_completion_models",
    phase=Phase.SERVICE,
    fn=_load_chat_completion_from_stored,
    severity=HookSeverity.DEGRADABLE,
    description="Load chat completion model implementations for all providers",
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
    name="clear_rerank_models",
    fn=_clear_rerank_models,
    description="Clear rerank model handler instances",
)

manager.register_shutdown(
    name="clear_chat_completion_models",
    fn=_clear_chat_completion_models,
    description="Clear chat completion model handler instances",
)

manager.register_shutdown(
    name="clear_text_embedding_models",
    fn=_clear_text_embedding_models,
    description="Clear text embedding model handler instances",
)

manager.register_shutdown(
    name="clear_model_schema_cache",
    fn=_clear_model_schema_cache,
    description="Clear model schema data cache",
)

manager.register_shutdown(
    name="clear_provider_cache",
    fn=_clear_provider_cache,
    description="Clear provider data cache",
)
