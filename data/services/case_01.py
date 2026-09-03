from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

app = FastAPI()

class CreateUserRequest(BaseModel):
    username: str
    email: Optional[str] = None  # VIOLATION: spec requires email as mandatory

@app.post("/users", status_code=201)
def create_user(body: CreateUserRequest):
    return {
        "id": 1,
        "username": body.username,
        "email": body.email,
    }
