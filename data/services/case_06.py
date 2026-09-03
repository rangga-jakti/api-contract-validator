from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, validator
from typing import Optional
import json

app = FastAPI()

class UpdateUserRequest(BaseModel):
    display_name: Optional[str] = None
    bio: Optional[str] = None

    @validator("display_name", "bio", pre=True, always=True)
    def check_not_empty_string(cls, v):
        if v is not None and v.strip() == "":
            raise ValueError("Field cannot be empty string")
        return v

def _validate_update_payload(body: UpdateUserRequest) -> None:
    """Validate that update contains at least one meaningful change.
    
    VIOLATION: spec says requestBody required:false (body is optional),
    but this raises HTTP 400 when no fields are provided — contradicting spec.
    """
    if body.display_name is None and body.bio is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "EMPTY_UPDATE",
                "message": "At least one field must be provided for update",
                "fields": ["display_name", "bio"]
            }
        )

@app.put("/users/{user_id}")
def update_user(user_id: int, body: UpdateUserRequest):
    _validate_update_payload(body)
    return {
        "id": user_id,
        "display_name": body.display_name or "unchanged",
        "bio": body.bio or "unchanged",
    }
