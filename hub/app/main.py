from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .routes import students
from .routes import students, clearance
from .db import init_db
init_db()


app = FastAPI(title="DNSC e-Clearance Hub")


# ─────────────────────────────────────────────
# 🔒 Global Error Handlers
# ─────────────────────────────────────────────

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": [{
                "loc": [],
                "msg": exc.detail,
                "type": f"HTTP_{exc.status_code}"
            }]
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc):
    errors = []
    for err in exc.errors():
        errors.append({
            "loc": list(err["loc"]),
            "msg": err["msg"],
            "type": err["type"]
        })
    return JSONResponse(
        status_code=422,
        content={"detail": errors}
    )


# ─────────────────────────────────────────────
# 🔓 Public Routes
# ─────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health():
    return {"status": "ok"}


# ─────────────────────────────────────────────
# 📍 API v1 Routes — from routes/students.py
# ─────────────────────────────────────────────

app.include_router(
    students.router,
    prefix="/students",
    tags=["Students"]
)

app.include_router(
    clearance.router,
    prefix="/clearance",
    tags=["Clearance"]
)