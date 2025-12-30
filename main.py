from fastapi import FastAPI, HTTPException, status, Path, Query
from pydantic import BaseModel
import sqlite3
from typing import Optional
from datetime import datetime, timedelta

app = FastAPI(
    title="Dental Clinic API",
    description="Voice Agent Appointment Booking",
    version="3.0"
)

DB_NAME = "clinic.db"
WORK_START = 8
WORK_END = 16
APPOINTMENT_DURATION = 60  # minutes

# ---------- Database ----------
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT NOT NULL,
            age INTEGER NOT NULL,
            service TEXT NOT NULL,
            appointment_date TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ---------- Models ----------
class AppointmentCreate(BaseModel):
    patient_name: str
    age: int
    service: str
    appointment_date: str  # YYYY-MM-DD HH:MM

class AppointmentUpdate(BaseModel):
    appointment_date: str

# ---------- Helpers ----------
def parse_date(date_str: str) -> datetime:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M")
    except ValueError:
        raise HTTPException(400, "صيغة التاريخ يجب أن تكون YYYY-MM-DD HH:MM")

def check_availability(conn, target_dt: datetime, exclude_id: int = None):
    start = (target_dt - timedelta(minutes=59)).strftime("%Y-%m-%d %H:%M")
    end = (target_dt + timedelta(minutes=59)).strftime("%Y-%m-%d %H:%M")

    query = """
        SELECT id FROM appointments
        WHERE appointment_date > ? AND appointment_date < ?
    """
    params = [start, end]

    if exclude_id:
        query += " AND id != ?"
        params.append(exclude_id)

    cursor = conn.execute(query, params)
    return cursor.fetchone() is None

# ---------- Health ----------
@app.get("/")
def get_all_appointments():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM appointments ORDER BY appointment_date"
    ).fetchall()
    conn.close()

    return {
        "count": len(rows),
        "appointments": [dict(row) for row in rows]
    }


# ---------- Availability ----------
@app.get("/availability")
def get_availability(date: str = Query(..., description="YYYY-MM-DD")):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT appointment_date FROM appointments WHERE appointment_date LIKE ?",
        (f"{date}%",)
    )
    booked = [datetime.strptime(r[0], "%Y-%m-%d %H:%M").hour for r in cursor.fetchall()]
    conn.close()

    slots = [
        f"{hour:02d}:00"
        for hour in range(WORK_START, WORK_END)
        if hour not in booked
    ]

    return {
        "date": date,
        "available_slots": slots
    }

# ---------- Create ----------
@app.post("/appointments", status_code=status.HTTP_201_CREATED)
def create_appointment(data: AppointmentCreate):
    dt = parse_date(data.appointment_date)

    if dt < datetime.now():
        raise HTTPException(400, "لا يمكن الحجز في الماضي")

    if not (WORK_START <= dt.hour < WORK_END):
        raise HTTPException(400, "خارج ساعات الدوام")

    conn = get_db()

    if not check_availability(conn, dt):
        conn.close()
        raise HTTPException(409, "الموعد غير متاح")

    conn.execute(
        """
        INSERT INTO appointments (patient_name, age, service, appointment_date)
        VALUES (?, ?, ?, ?)
        """,
        (data.patient_name, data.age, data.service, data.appointment_date)
    )
    conn.commit()
    conn.close()

    return {"status": "booked", "appointment_date": data.appointment_date}

# ---------- Get (Verify + Read) ----------
@app.get("/appointments")
def get_appointments(
    patient_name: Optional[str] = None,
    age: Optional[int] = None
):
    conn = get_db()
    query = "SELECT id, appointment_date, service FROM appointments WHERE 1=1"
    params = []

    if patient_name:
        query += " AND patient_name LIKE ?"
        params.append(f"%{patient_name}%")

    if age:
        query += " AND age = ?"
        params.append(age)

    query += " ORDER BY appointment_date"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    return {
        "count": len(rows),
        "appointments": [dict(row) for row in rows]
    }

# ---------- Get One ----------
@app.get("/appointments/{appointment_id}")
def get_appointment(appointment_id: int = Path(...)):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM appointments WHERE id = ?",
        (appointment_id,)
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(404, "الموعد غير موجود")

    return dict(row)

# ---------- Update ----------
@app.patch("/appointments/{appointment_id}")
def update_appointment(
    appointment_id: int,
    data: AppointmentUpdate
):
    new_dt = parse_date(data.appointment_date)

    conn = get_db()

    exists = conn.execute(
        "SELECT id FROM appointments WHERE id = ?",
        (appointment_id,)
    ).fetchone()

    if not exists:
        conn.close()
        raise HTTPException(404, "الموعد غير موجود")

    if not check_availability(conn, new_dt, appointment_id):
        conn.close()
        raise HTTPException(409, "التوقيت الجديد غير متاح")

    conn.execute(
        "UPDATE appointments SET appointment_date = ? WHERE id = ?",
        (data.appointment_date, appointment_id)
    )
    conn.commit()
    conn.close()

    return {"status": "updated", "new_date": data.appointment_date}

# ---------- Delete ----------
@app.delete("/appointments/{appointment_id}")
def delete_appointment(appointment_id: int):
    conn = get_db()
    cursor = conn.execute(
        "DELETE FROM appointments WHERE id = ?",
        (appointment_id,)
    )

    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(404, "الموعد غير موجود")

    conn.commit()
    conn.close()

    return {"status": "cancelled"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)