from enum import Enum
from pydantic import BaseModel
from typing import Dict, Optional, List
from .capabilities_engine import (
    derive_model_capabilities,
    allow_stream as caps_allow_stream,
    allow_tools as caps_allow_tools,
    allow_vision as caps_allow_vision,
    allow_json_schema as caps_allow_json_schema,
    supports_response_format as caps_supports_response_format,
)

__all__ = ["ModelType", "ModelSchema"]


class ModelType(str, Enum):
    CHAT_COMPLETION = "chat_completion"
    TEXT_EMBEDDING = "text_embedding"
    RERANK = "rerank"
    WILDCARD = "wildcard"


class ModelSchema(BaseModel):
    model_schema_id: str
    name: str
    description: str

    provider_id: str
    provider_model_id: Optional[str]

    type: ModelType
    properties: Optional[Dict]
    capabilities: Optional[Dict]
    allowed_configs: List[str]
    config_schemas: List[Dict]
    pricing: Optional[Dict]

    def get_capabilities(self) -> Dict:
        """
        Returns unified capabilities dict derived through the centralized
        backend engine. Priority (highest first):

          1. schema-level ``capabilities`` from inference response
          2. schema-level legacy ``properties`` (streaming/function_call/...)
          3. config_schemas heuristic (response_format → json_schema)
          4. provider-level defaults
          5. safe fallback defaults
        """
        return derive_model_capabilities(
            provider_id=self.provider_id,
            model_schema_id=self.model_schema_id,
            model_type=self.type.value if hasattr(self.type, "value") else str(self.type),
            schema_capabilities=self.capabilities,
            schema_properties=self.properties,
            config_schemas=self.config_schemas,
        )

    def allow_stream(self) -> bool:
        return caps_allow_stream(self.get_capabilities())

    def allow_function_call(self) -> bool:
        return caps_allow_tools(self.get_capabilities())

    def allow_vision_input(self) -> bool:
        return caps_allow_vision(self.get_capabilities())

    def allow_json_schema(self) -> bool:
        return caps_allow_json_schema(self.get_capabilities())

    def supports_response_format(self, fmt: str) -> bool:
        return caps_supports_response_format(self.get_capabilities(), fmt)

    @staticmethod
    def object_name():
        return "ModelSchema"

    @classmethod
    def build(cls, row: Dict):
        return cls(
            model_schema_id=row["model_schema_id"],
            name=row["name"] or "",
            description=row.get("description", ""),
            provider_id=row["provider_id"],
            provider_model_id=row["provider_model_id"],
            type=row["type"],
            properties=row.get("properties"),
            capabilities=row.get("capabilities"),
            allowed_configs=row.get("allowed_configs") or [],
            config_schemas=row.get("config_schemas") or [],
            pricing=row.get("pricing"),
        )

    def to_dict(self, lang: str):
        from app.services.model import i18n_text

        config_schemas = [
            {
                "config_id": config_schema["config_id"],
                "name": i18n_text("config_schema", config_schema["name"], lang),
                "description": i18n_text("config_schema", config_schema["description"], lang),
                "schema": config_schema["schema"],
            }
            for config_schema in self.config_schemas
        ]

        return {
            "object": self.object_name(),
            "model_schema_id": self.model_schema_id,
            "name": i18n_text(self.provider_id, self.name, lang),
            "description": i18n_text(self.provider_id, self.description, lang),
            "provider_id": self.provider_id,
            "provider_model_id": self.provider_model_id,
            "type": self.type.value,
            "properties": self.properties,
            "capabilities": self.get_capabilities(),
            "allowed_configs": self.allowed_configs,
            "config_schemas": config_schemas,
            "pricing": self.pricing,
        }
