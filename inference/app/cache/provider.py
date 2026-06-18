import logging
from typing import List, Optional, Dict
import os
from app.models import Provider
from app.models.yaml_loader import load_yaml_file, load_yaml_raw, load_yaml_files_from_dir, PROVIDERS_ROOT, load_providers_dir
from app.utils import checksum
from app.utils.i18n import set_i18n, collect_i18n_values
from app.error import raise_http_error, ErrorCode
from config import CONFIG

logger = logging.getLogger(__name__)

__all__ = [
    "list_providers",
    "get_provider",
    "load_provider_data",
    "get_provider_cache",
    "get_provider_checksum",
]

__providers: List = []
__provider_dict: Dict = {}
__providers_cache: List[Dict] = []
__provider_checksum: str = ""


def _read_provider_yaml(provider_id: str) -> Optional[Dict]:
    file_path = os.path.join(PROVIDERS_ROOT, provider_id, "resources/provider.yml")
    return load_yaml_file(file_path)


def _read_provider_yaml_raw(provider_id: str) -> Optional[str]:
    file_path = os.path.join(PROVIDERS_ROOT, provider_id, "resources/provider.yml")
    return load_yaml_raw(file_path)


def _collect_provider_i18n_keys(provider_id: str) -> List[str]:
    i18n_keys = []
    provider_str = _read_provider_yaml_raw(provider_id)
    if provider_str:
        i18n_keys.extend(collect_i18n_values(provider_str))

    model_schema_dir = os.path.join(PROVIDERS_ROOT, provider_id, "resources/models")
    for file_path, _ in load_yaml_files_from_dir(model_schema_dir):
        model_str = load_yaml_raw(file_path)
        if model_str:
            i18n_keys.extend(collect_i18n_values(model_str))

    return i18n_keys


def _load_provider_i18n(provider_id: str, i18n_keys: List[str]):
    i18n_dir_path = os.path.join(PROVIDERS_ROOT, provider_id, "resources/i18n")
    if not os.path.exists(i18n_dir_path):
        return
    for i18n_file in os.listdir(i18n_dir_path):
        if i18n_file.endswith(".yml"):
            lang = i18n_file.split(".")[0]
            i18n_data = load_yaml_file(os.path.join(i18n_dir_path, i18n_file))
            if i18n_data is None:
                continue
            for key in i18n_keys:
                if key[5:] not in i18n_data:
                    raise_http_error(
                        ErrorCode.OBJECT_NOT_FOUND,
                        f"{provider_id}'s i18n key {key[5:]} is missing in {i18n_file}",
                    )
            set_i18n(provider_id, lang, i18n_data)


def _build_provider(provider_id: str) -> Optional[Provider]:
    provider_dict = _read_provider_yaml(provider_id)
    if provider_dict is None:
        logger.debug("Skipping empty or missing provider.yml for provider: %s", provider_id)
        return None

    i18n_keys = _collect_provider_i18n_keys(provider_id)
    _load_provider_i18n(provider_id, i18n_keys)

    return Provider.build(provider_dict)


def _should_skip_provider(provider_id: str) -> bool:
    if CONFIG.ALLOWED_PROVIDERS and provider_id not in CONFIG.ALLOWED_PROVIDERS:
        return True
    if provider_id == "debug" and CONFIG.PROD:
        return True
    return False


def load_provider_data() -> List[str]:
    global __providers, __provider_dict, __providers_cache, __provider_checksum

    all_provider_ids = load_providers_dir()

    for provider_id in all_provider_ids:
        if _should_skip_provider(provider_id):
            continue
        logger.info("Loading provider data from providers/%s/resources/provider.yml", provider_id)
        try:
            provider = _build_provider(provider_id)
            if provider is not None:
                __provider_dict[provider_id] = provider
                __providers.append(provider)
        except Exception as e:
            logger.error("Error loading provider %s: %s", provider_id, e)

    __providers.sort(key=lambda x: x.provider_id)
    __providers_cache = [provider.to_dict(lang=None) for provider in __providers]
    __provider_checksum = checksum(__providers_cache)
    return all_provider_ids


def list_providers() -> List[Provider]:
    return __providers


def get_provider(provider_id: str) -> Optional[Provider]:
    return __provider_dict.get(provider_id)


def get_provider_cache() -> List[Dict]:
    return __providers_cache


def get_provider_checksum() -> str:
    return __provider_checksum
