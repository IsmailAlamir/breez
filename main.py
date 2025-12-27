from fastapi import FastAPI, HTTPException, status, Path
from pydantic import BaseModel, Field
import sqlite3
from typing import Optional, List
from datetime import datetime

app = FastAPI(
    title="Breez Dental Clinic API",
    description="A secure, RESTful API for managing dental appointments with Identity Verification.",
    version="2.0"
)

DB_NAME = "dental_clinic.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row 
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT NOT NULL,
            age INTEGER NOT NULL,
            service TEXT NOT NULL,
            appointment_date TEXT NOT NULL,
            insurance_provider TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

class BookingRequest(BaseModel):
    patient_name: str = Field(..., min_length=2, description="اسم المريض")
    age: int = Field(..., gt=0, le=120, description="العمر للتحقق من الهوية")
    service: str
    appointment_date: str
    insurance_provider: Optional[str] = "None"
    notes: Optional[str] = ""

class VerifyRequest(BaseModel):
    patient_name: str
    age: int

class RescheduleRequest(BaseModel):
    new_date: str

class AppointmentResponse(BaseModel):
    id: int
    patient_name: str
    service: str
    appointment_date: str
    status: str
    message: str


@app.get("/")
def health_check():
    """Health check endpoint"""
    return {"status": "operational", "system": "Breez Dental Backend"}

@app.post("/appointments", status_code=status.HTTP_201_CREATED)
def create_appointment(booking: BookingRequest):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM appointments WHERE patient_name = ? AND appointment_date = ?",
        (booking.patient_name, booking.appointment_date)
    )
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail="يوجد موعد مسجل مسبقاً لهذا المريض في نفس التوقيت")

    cursor.execute(
        """
        INSERT INTO appointments (patient_name, age, service, appointment_date, insurance_provider, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (booking.patient_name, booking.age, booking.service, booking.appointment_date, booking.insurance_provider, booking.notes)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    return {"status": "success", "id": new_id, "message": "تم تأكيد الحجز بنجاح"}

@app.post("/verify")
def verify_identity_and_find_appointment(data: VerifyRequest):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, appointment_date, service FROM appointments WHERE patient_name LIKE ? AND age = ?",
        (f"%{data.patient_name}%", data.age)
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return {"status": "not_found", "message": "لم يتم العثور على حجز مطابق للاسم والعمر."}

    results = [dict(row) for row in rows]
    
    return {"status": "found", "count": len(results), "appointments": results, "message": "تم التحقق من الهوية."}

@app.patch("/appointments/{appointment_id}")
def reschedule_appointment(
    appointment_id: int = Path(..., description="The ID obtained from verification step"),
    update_data: RescheduleRequest = None
):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM appointments WHERE id = ?", (appointment_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="الموعد غير موجود")

    cursor.execute(
        "UPDATE appointments SET appointment_date = ? WHERE id = ?",
        (update_data.new_date, appointment_id)
    )
    conn.commit()
    conn.close()

    return {"status": "success", "message": f"تم تعديل الموعد إلى {update_data.new_date}"}

@app.delete("/appointments/{appointment_id}")
def cancel_appointment(appointment_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM appointments WHERE id = ?", (appointment_id,))
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="الموعد غير موجود أو تم حذفه مسبقاً")

    conn.commit()
    conn.close()
    return {"status": "success", "message": "تم إلغاء الموعد بنجاح"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)