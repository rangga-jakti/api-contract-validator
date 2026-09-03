from fastapi import FastAPI

app = FastAPI()

REPORTS = [{"id": i, "title": f"Report {i}"} for i in range(1, 51)]

# VIOLATION: spec defines 'page' and 'limit' query params,
# but code uses 'offset' and 'count' instead
@app.get("/reports")
def list_reports(offset: int = 0, count: int = 20):
    paginated = REPORTS[offset:offset + count]
    return {
        "data": paginated,
        "offset": offset,
        "total": len(REPORTS),
    }
