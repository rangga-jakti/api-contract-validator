from fastapi import FastAPI
from typing import List
from enum import Enum

app = FastAPI()

class AccessLevel(str, Enum):
    """Access level enum - stored as string internally."""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"

class Resource:
    def __init__(self, rid: int, name: str, level: AccessLevel):
        self.resource_id = rid
        self.resource_name = name
        self.access_level = level  # VIOLATION: spec says integer, this is string enum

    def to_dict(self) -> dict:
        return {
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "access_level": self.access_level.value,  # returns "read"/"write" string
        }

PERMISSION_STORE = {
    1: [Resource(1, "documents", AccessLevel.WRITE), Resource(2, "reports", AccessLevel.READ)],
    2: [Resource(3, "analytics", AccessLevel.READ)],
}

@app.get("/users/{user_id}/permissions")
def get_permissions(user_id: int):
    resources = PERMISSION_STORE.get(user_id, [])
    return {
        "user_id": user_id,
        "role": "editor",
        "permissions": {
            "resources": [r.to_dict() for r in resources]
        }
    }
