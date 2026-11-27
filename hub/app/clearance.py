from typing import List, Dict, Any


def evaluate_clearance(student: Dict[str, Any]) -> Dict[str, Any]:
    """Decide: Is this student CLEARED or ON HOLD?"""
    reasons: List[str] = []
    student_id = student.get("student_id", "UNKNOWN")
    
    # Rule 1: Not ENROLLED → HOLD
    if student.get("status") != "ENROLLED":
        reasons.append("NEEDS_REVIEW")
    
    # Rule 2: Check year level
    year_level = student.get("year_level")
    if not year_level or not isinstance(year_level, int) or year_level < 1 or year_level > 4:
        reasons.append("NO_ACCOUNTING_RECORD")
    
    # Rule 3: Demo — odd last digit = UNPAID_FINES
    last_digit = student_id[-1]
    if last_digit in "13579":
        reasons.append("UNPAID_FINES")
    
    status = "CLEARED" if not reasons else "HOLD"
    
    return {
        "student_id": student_id,
        "status": status,
        "reasons": reasons
    }
