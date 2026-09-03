from fastapi import FastAPI

app = FastAPI()

@app.delete("/orders/{order_id}")  # VIOLATION: returns 200 with body, spec says 204 no content
def cancel_order(order_id: int):
    return {"message": "Order cancelled", "order_id": order_id}
