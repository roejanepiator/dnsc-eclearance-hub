from fastapi import APIRouter, HTTPException
from ..registrar_client import RegistrarClient, RegistrarError
from ..clearance import evaluate_clearance  # ← IMPORTS the function above

router = APIRouter()
registrar = RegistrarClient()

@router.get("/{student_id}")
def get_clearance_status(student_id: str):
    try:
        student = registrar.get_student(student_id)
    except RegistrarError as e:
        raise HTTPException(status_code=502, detail=str(e))
    if student is None:
        raise HTTPException(status_code=404, detail="student not found")
    return evaluate_clearance(student)
