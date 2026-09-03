from fastapi import FastAPI
from typing import List, Dict, Any
import math, hashlib

app = FastAPI()

def _compute_price_index(base: float, category: str) -> float:
    """Internal pricing calculation - not exposed to API consumers."""
    multiplier = {"widgets": 1.0, "premium": 2.5, "bulk": 0.7}.get(category, 1.0)
    return round(base * multiplier * (1 + 0.1 * math.log(base + 1)), 2)

def _build_product_record(raw: dict) -> dict:
    """Transform raw DB record to API response format."""
    return {
        "id": raw["product_id"],
        "name": raw["display_name"],
        "cost": _compute_price_index(raw["base_price"], raw["cat"]),  # VIOLATION: spec says 'price'
        "category": raw["cat"],
    }

RAW_DB = [
    {"product_id": 1, "display_name": "Widget A", "base_price": 9.99, "cat": "widgets"},
    {"product_id": 2, "display_name": "Widget B", "base_price": 14.99, "cat": "premium"},
]

@app.get("/products")
def list_products():
    return [_build_product_record(r) for r in RAW_DB]
