import os
import importlib
from typing import List
import logging
from app.models.yaml_loader import PROVIDERS_ROOT

logger = logging.getLogger(__name__)

__all__ = [
    "get_chat_completion_model",
    "load_all_chat_completion_models",
]

models = {}


def __get_provider_model_class(provider_id: str):
    class_name = "".join(word.title() for word in provider_id.split("_")) + "ChatCompletionModel"
    module = importlib.import_module(f"providers.{provider_id}.chat_completion")
    return getattr(module, class_name)


def get_chat_completion_model(provider_id: str):
    if provider_id in models:
        return models[provider_id]

    model_class = __get_provider_model_class(provider_id)
    models[provider_id] = model_class()

    return models[provider_id]


def load_all_chat_completion_models(provider_ids: List[str]):
    for provider_id in provider_ids:
        provider_path = os.path.join(PROVIDERS_ROOT, provider_id)
        if os.path.isdir(provider_path) and os.path.exists(os.path.join(provider_path, "chat_completion.py")):
            try:
                get_chat_completion_model(provider_id)
                logger.info("Loaded chat completion models from %s", provider_id)
            except Exception as e:
                logger.error("load_all_chat_completion_models: Error loading chat completion models from %s: %s", provider_id, e)
