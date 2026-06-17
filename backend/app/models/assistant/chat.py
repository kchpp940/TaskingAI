from typing import Dict, List, Optional

from pydantic import Field

from tkhelper.models import ModelEntity
from tkhelper.utils import load_json_attr, generate_random_id
from tkhelper.schemas.field import *

from app.database import redis_conn
from .assistant import Assistant
from .memory import ChatMemory

__all__ = ["Chat"]


class Chat(ModelEntity):
    object: str = "Chat"
    assistant_id: str = id_field("assistant", length=24)
    chat_id: str = id_field("chat", length=24)

    metadata: Dict = metadata_field()
    memory: ChatMemory = Field(...)
    name: str = name_field("chat")

    created_timestamp: int = created_timestamp_field()
    updated_timestamp: int = updated_timestamp_field()

    @staticmethod
    def build(row):
        return Chat(
            # ids
            chat_id=row["chat_id"],
            assistant_id=row["assistant_id"],
            # data
            memory=load_json_attr(row, "memory", {}),
            metadata=load_json_attr(row, "metadata", {}),
            name=row.get("name") or "",
            # timestamps
            created_timestamp=row["created_timestamp"],
            updated_timestamp=row["updated_timestamp"],
        )

    def to_response_dict(self) -> Dict:
        return {
            "object": "Chat",
            "assistant_id": self.assistant_id,
            "chat_id": self.chat_id,
            "metadata": self.metadata,
            "memory": self.memory,
            "name": self.name,
            "created_timestamp": self.created_timestamp,
            "updated_timestamp": self.updated_timestamp,
        }

    @staticmethod
    def object_name() -> str:
        return "chat"

    @staticmethod
    def object_plural_name() -> str:
        return "chats"

    @staticmethod
    def table_name() -> str:
        return "chat"

    @staticmethod
    def id_field_name() -> str:
        return "chat_id"

    @staticmethod
    def primary_key_fields() -> List[str]:
        return ["assistant_id", "chat_id"]

    @staticmethod
    def generate_random_id(**kwargs) -> str:
        return "SdEL" + generate_random_id(20)

    @staticmethod
    def list_prefix_filter_fields() -> List[str]:
        return []

    @staticmethod
    def parent_models() -> List:
        return [Assistant]

    @staticmethod
    def parent_operator() -> List:
        from app.operators import assistant_ops

        return [assistant_ops]

    @staticmethod
    def create_fields() -> List[str]:
        return ["metadata", "name"]

    @staticmethod
    def update_fields() -> List[str]:
        return ["metadata", "name"]

    @staticmethod
    def fields_exclude_in_response():
        return []

    def __lock_redis_key(self):
        return f"chat:{self.assistant_id}:{self.chat_id}:lock"

    async def is_chat_locked(self) -> bool:
        return await redis_conn.get_string(key=self.__lock_redis_key()) is not None

    async def lock(self) -> Optional[str]:
        """
        Atomically acquire the chat lock.
        :return: lock owner token string if acquired, None if already locked
        """
        token = generate_random_id(32)
        acquired = await redis_conn.set_string_if_not_exists(
            key=self.__lock_redis_key(),
            value=token,
            expire=120,
        )
        return token if acquired else None

    async def unlock(self, token: str) -> bool:
        """
        Release the chat lock only if the provided token matches the current lock owner.
        Uses a Lua script for atomic compare-and-delete.
        :param token: the lock owner token returned by lock()
        :return: True if lock was released by this call, False if token didn't match or key didn't exist
        """
        return await redis_conn.delete_if_equals(key=self.__lock_redis_key(), value=token)
