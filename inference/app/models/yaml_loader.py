import os
import yaml
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

__all__ = [
    "load_yaml_file",
    "load_yaml_files_from_dir",
    "load_providers_dir",
    "PROVIDERS_ROOT",
]

PROVIDERS_ROOT = os.path.join(os.path.dirname(os.path.realpath(__file__)), "../../providers")


def load_yaml_file(file_path: str) -> Optional[Dict]:
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return None
    try:
        with open(file_path, "r") as f:
            data = yaml.safe_load(f)
        return data
    except yaml.YAMLError as e:
        logger.error("Error loading YAML from file %s: %s", file_path, e)
        return None


def load_yaml_raw(file_path: str) -> Optional[str]:
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return None
    try:
        with open(file_path, "r") as f:
            return f.read()
    except Exception as e:
        logger.error("Error reading file %s: %s", file_path, e)
        return None


def load_yaml_files_from_dir(dir_path: str) -> List[Tuple[str, Dict]]:
    results = []
    if not os.path.exists(dir_path):
        return results
    for file_name in sorted(os.listdir(dir_path)):
        if not file_name.endswith(".yml"):
            continue
        file_path = os.path.join(dir_path, file_name)
        data = load_yaml_file(file_path)
        if data is not None:
            results.append((file_path, data))
    return results


def load_providers_dir() -> List[str]:
    import re

    if not os.path.exists(PROVIDERS_ROOT):
        return []
    pattern = re.compile(r"^[a-z0-9][a-z0-9_]*$")
    provider_ids = [
        i
        for i in os.listdir(PROVIDERS_ROOT)
        if os.path.isdir(os.path.join(PROVIDERS_ROOT, i)) and pattern.match(i) and not i.startswith("template")
    ]
    return sorted(provider_ids)
