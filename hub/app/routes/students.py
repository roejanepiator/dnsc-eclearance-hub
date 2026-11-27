from fastapi import APIRouter, HTTPException, Query
from ..registrar_client import RegistrarClient, RegistrarError

router = APIRouter()
registrar = RegistrarClient()


def mask_id(sid: str) -> str:
    if not sid or len(sid) < 8:
        return sid
    return sid[:4] + "-***" + sid[-4:]


@router.get("")
def list_students(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=50)):
    try:
        all_students = registrar.get_all_students()
        
        masked_students = []
        for s in all_students:
            masked = s.copy()
            masked["student_id"] = mask_id(s["student_id"])
            masked_students.append(masked)
        
        total = len(masked_students)
        start = (page - 1) * size
        end = start + size
        paginated = masked_students[start:end]
        
        return {
            "page": page,
            "size": size,
            "total": total,
            "has_next": end < total,
            "data": paginated
        }
    except RegistrarError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/{student_id}")
def get_one_student(student_id: str):
    try:
        student = registrar.get_student(student_id)
    except RegistrarError as e:
        raise HTTPException(status_code=502, detail=str(e))
    if student is None:
        raise HTTPException(status_code=404, detail="student not in Registrar masterlist")
    return student
