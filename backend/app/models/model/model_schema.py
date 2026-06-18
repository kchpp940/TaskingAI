from enum import Enum
from pydantic import BaseModel
from typing import Dict, Optional, List

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

    def allow_stream(self) -> bool:
        if self.capabilities:
            return bool(self.capabilities.get("stream", False))
        return bool(self.properties and self.properties.get("streaming", False))

    def allow_function_call(self) -> bool:
        if self.capabilities:
            return bool(self.capabilities.get("tools", False))
        return bool(self.properties and self.properties.get("function_call", False))

    def allow_vision_input(self) -> bool:
        if self.capabilities:
            return bool(self.capabilities.get("vision", False))
        return bool(self.properties and self.properties.get("vision", False))

    def allow_json_schema(self) -> bool:
        if self.capabilities:
            return bool(self.capabilities.get("json_schema", False))
        return bool(self.properties and self.properties.get("json_schema", False))

    def get_capabilities(self) -> Dict:
        """Return capabilities dict, constructing from legacy properties if missing."""
        if self.capabilities:
            return self.capabilities
        caps = {}
        props = self.properties or {}
        caps["stream"] = props.get("streaming", False)
        caps["tools"] = props.get("function_call", False)
        caps["vision"] = props.get("vision", False)
        caps["json_schema"] = props.get("json_schema", False)
        if "input_token_limit" in props:
            caps["max_context_tokens"] = props["input_token_limit"]
        if "output_token_limit" in props:
            caps["max_output_tokens"] = props["output_token_limit"]
        caps["supported_response_formats"] = props.get(
            "supported_response_formats", ["text"]
        )
        if caps["json_schema"] and "json_schema" not in caps["supported_response_formats"]:
            caps["supported_response_formats"] = [*caps["supported_response_formats"], "json_schema"]
        return caps

    def supports_response_format(self, fmt: str) -> bool:
        return fmt in self.get_capabilities().get("supported_response_formats", [])

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
