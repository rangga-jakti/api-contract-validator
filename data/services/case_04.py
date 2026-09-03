from fastapi import FastAPI

app = FastAPI()

ITEMS = [
    {"id": 1, "name": "Bolt M8", "stock": 500},
    {"id": 2, "name": "Nut M8", "stock": 300},
]

@app.get("/items")
def list_items():
    return ITEMS

@app.get("/health")  # VIOLATION: endpoint exists in code but not documented in spec
def health_check():
    return {"status": "ok", "version": "1.0"}
