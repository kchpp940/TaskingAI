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
    allowed_configs: List[str]
    config_schemas: List[Dict]
    pricing: Optional[Dict]

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
            allowed_configs=row.get("allowed_configs") or [],
            config_schemas=row.get("config_schemas") or [],
            pricing=row.get("pricing"),
        )

    def to_dict(self, lang: str):
        from app.services.model import i18n_text
        from app.services.model.capability import CapabilityEvaluationService

        config_schemas = [
            {
                "config_id": config_schema["config_id"],
                "name": i18n_text("config_schema", config_schema["name"], lang),
                "description": i18n_text("config_schema", config_schema["description"], lang),
                "schema": config_schema["schema"],
            }
            for config_schema in self.config_schemas
        ]

        capabilities = CapabilityEvaluationService.evaluate_model_schema_capabilities(
            model_schema_type=self.type.value,
            model_schema_properties=self.properties,
        )

        return {
            "object": self.object_name(),
            "model_schema_id": self.model_schema_id,
            "name": i18n_text(self.provider_id, self.name, lang),
            "description": i18n_text(self.provider_id, self.description, lang),
            "provider_id": self.provider_id,
            "provider_model_id": self.provider_model_id,
            "type": self.type.value,
            "properties": self.properties,
            "normalized_capabilities": capabilities.model_dump(exclude_none=True),
            "capability_incompatibility_reasons": self._build_unsupported_capabilities(capabilities),
            "allowed_configs": self.allowed_configs,
            "config_schemas": config_schemas,
            "pricing": self.pricing,
        }

    def _build_unsupported_capabilities(self, capabilities) -> List[Dict]:
        reasons = []
        if self.type in (ModelType.CHAT_COMPLETION, ModelType.WILDCARD):
            if not capabilities.streaming:
                reasons.append({"capability": "streaming", "reason": "Streaming output is not declared as supported by this model schema."})
            if not capabilities.function_call:
                reasons.append({"capability": "function_call", "reason": "Function/tool calling is not declared as supported by this model schema."})
            if not capabilities.vision:
                reasons.append({"capability": "vision", "reason": "Vision/image input is not declared as supported by this model schema."})
            if not capabilities.response_format:
                reasons.append({"capability": "response_format", "reason": "JSON mode / structured response format is not declared as supported. Only explicitly declared via schema capabilities or model override counts, not allowed_configs."})
        return reasons
