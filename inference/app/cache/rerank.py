from typing import List
import importlib
import os
import logging
from app.models.yaml_loader import PROVIDERS_ROOT

logger = logging.getLogger(__name__)

models = {}


def get_provider_model_class(provider_id: str):
    class_name = "".join(word.title() for word in provider_id.split("_")) + "RerankModel"
    module = importlib.import_module(f"providers.{provider_id}.rerank")
    return getattr(module, class_name)


def get_rerank_model(provider_id: str):
    if provider_id not in models:
        model_class = get_provider_model_class(provider_id)
        models[provider_id] = model_class()

    return models[provider_id]


def load_all_rerank_models(provider_ids: List[str]):
    for provider_id in provider_ids:
        provider_path = os.path.join(PROVIDERS_ROOT, provider_id)
        if os.path.isdir(provider_path) and os.path.exists(os.path.join(provider_path, "rerank.py")):
            try:
                get_rerank_model(provider_id)
                logger.info("Loaded rerank models from %s", provider_id)
            except Exception as e:
                logger.error("load_all_rerank_models: Error loading rerank models from %s: %s", provider_id, e)
