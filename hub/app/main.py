from fastapi import FastAPI, HTTPException

from .registrar_client import RegistrarClient, RegistrarError

app = FastAPI(title="DNSC e-Clearance Hub")
registrar = RegistrarClient()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/students")
def list_students():
    try:
        return registrar.get_all_students()
    except RegistrarError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/students/{student_id}")
def one_student(student_id: str):
    try:
        student = registrar.get_student(student_id)
    except RegistrarError as e:
        raise HTTPException(status_code=502, detail=str(e))
    if student is None:
        raise HTTPException(status_code=404, detail="student not in Registrar masterlist")
    return student
