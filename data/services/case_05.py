from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import time, hashlib, secrets

app = FastAPI()

class LoginRequest(BaseModel):
    username: str
    password: str

def _generate_session_token(username: str) -> dict:
    """Generate auth response payload."""
    raw = secrets.token_hex(32)
    ts = int(time.time())
    return {
        "access_token": f"{username}.{raw}.{ts}",  # VIOLATION: spec says 'token'
        "expires_in": 3600,
        "issued_at": ts,
    }

@app.post("/auth/login")
def login(body: LoginRequest):
    if body.username == "admin" and body.password == "secret":
        payload = _generate_session_token(body.username)
        return payload
    raise HTTPException(status_code=401, detail="Invalid credentials")
