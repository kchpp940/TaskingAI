from abc import ABC, abstractmethod
from typing import Optional, List
from app.models import ProviderCredentials
import importlib
import os
import logging
from app.models.yaml_loader import PROVIDERS_ROOT

logger = logging.getLogger(__name__)

models = {}


def get_provider_model_class(provider_id: str):
    class_name = "".join(word.title() for word in provider_id.split("_")) + "TextEmbeddingModel"
    module = importlib.import_module(f"providers.{provider_id}.text_embedding")
    return getattr(module, class_name)


def get_text_embedding_model(provider_id: str):
    if provider_id not in models:
        model_class = get_provider_model_class(provider_id)
        models[provider_id] = model_class()

    return models[provider_id]


def load_all_text_embedding_models(provider_ids: List[str]):
    for provider_id in provider_ids:
        provider_path = os.path.join(PROVIDERS_ROOT, provider_id)
        if os.path.isdir(provider_path) and os.path.exists(os.path.join(provider_path, "text_embedding.py")):
            try:
                get_text_embedding_model(provider_id)
                logger.info("Loaded text embedding models from %s", provider_id)
            except Exception as e:
                logger.error("load_all_text_embedding_models: Error loading text embedding models from %s: %s", provider_id, e)
