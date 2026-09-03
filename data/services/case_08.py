from fastapi import FastAPI

app = FastAPI()

NOTIFICATIONS = [
    {"id": 1, "message": "Your order has shipped", "read": False},
    {"id": 2, "message": "New message from support", "read": True},
]

@app.get("/notifications")
def get_notifications():
    return NOTIFICATIONS

@app.post("/notifications/{notification_id}/read")
def mark_as_read(notification_id: int):
    for n in NOTIFICATIONS:
        if n["id"] == notification_id:
            n["read"] = True
            return {"id": n["id"], "read": n["read"]}
    return {"id": notification_id, "read": True}
