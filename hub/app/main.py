from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .registrar_client import RegistrarClient, RegistrarError
#from .routes import students   ← we'll create/use this next


app = FastAPI(title="DNSC e-Clearance Hub")
registrar = RegistrarClient()


# ─────────────────────────────────────────────
# 🔒 Global Error Handlers — Contract Standard Format
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
# 🔓 Public Routes — no /api/v1 prefix
# ─────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


# ─────────────────────────────────────────────
# 📍 API v1 Routes — with prefix
# ─────────────────────────────────────────────

# Temporary: keep your working endpoints here first
@app.get("/api/v1/students")
def list_students():
    try:
        return registrar.get_all_students()
    except RegistrarError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/v1/students/{student_id}")
def one_student(student_id: str):
    try:
        student = registrar.get_student(student_id)
    except RegistrarError as e:
        raise HTTPException(status_code=502, detail=str(e))
    if student is None:
        raise HTTPException(status_code=404, detail="student not in Registrar masterlist")
    return student
